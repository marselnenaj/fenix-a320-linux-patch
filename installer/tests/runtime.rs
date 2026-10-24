// SPDX-License-Identifier: MIT
//! Real child processes and inherited image descriptors; no Wine or game needed.
use std::{
    fs::{self, File},
    io::{Seek, SeekFrom, Write},
    os::{fd::AsRawFd, unix::fs::PermissionsExt},
    path::Path,
    process::Command,
};
fn put(path: &Path, data: &[u8]) {
    fs::create_dir_all(path.parent().expect("parent")).expect("directory");
    fs::write(path, data).expect("fixture");
}
#[test]
fn native_and_portable_launch_keep_licensed_images_off_disk_and_clean_up() {
    for portable in [false, true] {
        let temp = tempfile::tempdir().expect("fixture");
        let root = temp.path();
        put(
            &root.join("private/runtime.json"),
            br#"{"game_id":"msfs2024","market":"DE"}"#,
        );
        fs::create_dir_all(root.join("local/msfs-prefix")).expect("prefix");
        let image = root.join("games/MSFS2024/FlightSimulator2024.exe");
        put(&image, b"encrypted original remains untouched");
        let mut payload = File::options()
            .read(true)
            .write(true)
            .create_new(true)
            .open(root.join("synthetic-image"))
            .expect("image fd");
        let mut header = vec![0; 256];
        header[..2].copy_from_slice(b"MZ");
        header[60..64].copy_from_slice(&64u32.to_le_bytes());
        header[64..68].copy_from_slice(b"PE\0\0");
        header[148..152].copy_from_slice(&256u32.to_le_bytes());
        payload.write_all(&header).expect("header");
        payload.set_len(4096).expect("size");
        payload.seek(SeekFrom::Start(512)).expect("offset");
        payload
            .write_all(b"SYNTHETIC LICENSED IMAGE")
            .expect("payload");
        let runner = root.join("runner/files/bin/wine");
        put(
            &runner,
            br##"#!/bin/sh
set -eu
test "$(head -c 2 "$1")" = MZ
test "$XODUS_STORE_PACKAGE_SCOPE" = FlightdeckBaseGameOnlyV1
if test "$FLIGHTDECK_PROTON_LOADER" = portable; then
    test -L "$1"
    test -z "${WINE_DLL_FILE_MAP-}"
else
    test -f "$1"
    test ! -L "$1"
    test -n "$WINE_DLL_FILE_MAP"
fi
exit 23
"##,
        );
        fs::set_permissions(&runner, fs::Permissions::from_mode(0o755)).expect("executable");
        rustix::io::fcntl_setfd(&payload, rustix::io::FdFlags::empty())
            .expect("inherit fixture fd");
        let map = format!(
            "{}:\\??\\Z:{}",
            payload.as_raw_fd(),
            image.to_string_lossy().replace('/', "\\")
        );
        let result = Command::new(env!("CARGO_BIN_EXE_fenix-runtime"))
            .env_clear()
            .env("PATH", "/usr/bin:/bin")
            .env("WINEPREFIX", root.join("local/msfs-prefix"))
            .env("XODUS_WINE_RUNNER", &runner)
            .env("WINE_DLL_FILE_MAP", map)
            .env(
                "FLIGHTDECK_PROTON_LOADER",
                if portable { "portable" } else { "native" },
            )
            .args(["wine-launch", "--runtime"])
            .arg(root)
            .arg("--")
            .arg(&image)
            .output()
            .expect("runtime");
        rustix::io::fcntl_setfd(&payload, rustix::io::FdFlags::CLOEXEC)
            .expect("restore fixture fd");
        assert_eq!(
            result.status.code(),
            Some(23),
            "{}",
            String::from_utf8_lossy(&result.stderr)
        );
        assert_eq!(
            fs::read(&image).expect("original"),
            b"encrypted original remains untouched"
        );
        assert!(
            !fs::read_dir(image.parent().expect("game"))
                .expect("entries")
                .any(|p| p
                    .expect("entry")
                    .file_name()
                    .to_string_lossy()
                    .starts_with(".xodus-launch-"))
        );
    }
}

#[test]
fn invalid_runtime_never_launches_a_child() {
    let temp = tempfile::tempdir().expect("fixture");
    put(
        &temp.path().join("private/runtime.json"),
        br#"{"game_id":"unsupported","market":"DE"}"#,
    );
    let result = Command::new(env!("CARGO_BIN_EXE_fenix-runtime"))
        .args(["game-launch", "--runtime"])
        .arg(temp.path())
        .output()
        .expect("runtime");
    assert_eq!(result.status.code(), Some(1));
    assert!(String::from_utf8_lossy(&result.stderr).contains("Invalid configured game"));
}
