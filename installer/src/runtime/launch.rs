// SPDX-License-Identifier: MIT
//! Preserve Xodus' licensed descriptors for the lifetime of the Wine process.
use super::{ensure, json, wine_binary};
use crate::{Error, Result};
use rustix::io::{FdFlags, fcntl_setfd};
use std::{
    collections::{BTreeMap, BTreeSet},
    ffi::OsString,
    fs::{self, File, OpenOptions},
    io::Write,
    os::{
        fd::AsRawFd,
        unix::{
            fs::{DirBuilderExt, FileExt, symlink},
            process::{CommandExt, ExitStatusExt},
        },
    },
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::atomic::{AtomicBool, AtomicUsize, Ordering},
    time::{Duration, Instant},
};
fn nt(path: &Path) -> Result<String> {
    Ok(format!(
        r"\??\Z:{}",
        path.to_str()
            .ok_or_else(|| Error::other("Invalid game path"))?
            .replace('/', "\\")
    ))
}
fn decoded(value: &str) -> PathBuf {
    value
        .strip_prefix(r"\??\Z:\")
        .map(|v| PathBuf::from(format!("/{}", v.replace('\\', "/"))))
        .unwrap_or_else(|| PathBuf::from(value))
}
fn configuration(root: &Path) -> Result<(String, String)> {
    let info = json(&root.join("private/runtime.json"), 65536)?;
    let game = info["game_id"].as_str().unwrap_or("msfs2024");
    ensure(
        ["msfs2024", "msfs2020"].contains(&game),
        "Invalid configured game",
    )?;
    let market = info["market"]
        .as_str()
        .ok_or_else(|| Error::other("Invalid configured market"))?;
    ensure(
        market.len() == 2 && market.bytes().all(|v| v.is_ascii_uppercase()),
        "Invalid configured market",
    )?;
    Ok((game.into(), market.into()))
}
fn game_paths(id: &str) -> (&'static str, &'static str) {
    if id == "msfs2020" {
        ("MSFS2020", "FlightSimulator.exe")
    } else {
        ("MSFS2024", "FlightSimulator2024.exe")
    }
}
struct Mapping {
    file: File,
    name: String,
}
fn mappings(value: &str) -> Result<Vec<Mapping>> {
    ensure(
        !value.is_empty() && value.len() <= 2 * 1024 * 1024,
        "Missing or invalid WINE_DLL_FILE_MAP",
    )?;
    let mut descriptors = BTreeMap::new();
    let mut result = Vec::new();
    for item in value.split('|') {
        let (number, name) = item
            .split_once(':')
            .ok_or_else(|| Error::other("Invalid image mapping"))?;
        ensure(
            !number.is_empty()
                && number.bytes().all(|v| v.is_ascii_digit())
                && result.len() < 16384,
            "Invalid image descriptor",
        )?;
        let number = number
            .parse::<u32>()
            .map_err(|_| Error::other("Invalid image descriptor"))?;
        if let std::collections::btree_map::Entry::Vacant(entry) = descriptors.entry(number) {
            let file = File::open(format!("/proc/self/fd/{number}"))?;
            ensure(
                file.metadata()?.is_file(),
                "Mapped image is not a regular file",
            )?;
            entry.insert(file);
        }
        result.push(Mapping {
            file: descriptors[&number].try_clone()?,
            name: name.into(),
        });
    }
    Ok(result)
}
fn headers(file: &File) -> Result<Vec<u8>> {
    let mut dos = [0; 64];
    file.read_exact_at(&mut dos, 0)?;
    ensure(
        &dos[..2] == b"MZ",
        "Mapped entry point is not a PE executable",
    )?;
    let offset = u64::from(u32::from_le_bytes(
        dos[60..64]
            .try_into()
            .map_err(|_| Error::other("Invalid PE header"))?,
    ));
    ensure(offset <= 1024 * 1024, "Invalid PE header offset")?;
    let mut pe = [0; 88];
    file.read_exact_at(&mut pe, offset)?;
    ensure(&pe[..4] == b"PE\0\0", "Invalid PE signature")?;
    let length = u64::from(u32::from_le_bytes(
        pe[84..88]
            .try_into()
            .map_err(|_| Error::other("Invalid PE header"))?,
    ));
    ensure(
        (offset + 88..=file.metadata()?.len().min(1024 * 1024)).contains(&length),
        "Invalid PE header length",
    )?;
    let mut result = vec![0; length as usize];
    file.read_exact_at(&mut result, 0)?;
    Ok(result)
}
struct View(PathBuf);
impl Drop for View {
    fn drop(&mut self) {
        let _ = fs::remove_dir_all(&self.0);
    }
}
fn skip(path: &Path, view: &Path) -> bool {
    path == view
        || path.file_name().is_some_and(|v| {
            let n = v.to_string_lossy();
            n.starts_with(".xodus-launch-") || n.starts_with(".xodus-fenix-")
        })
}
fn portable(source: &Path, view: &Path, mapped: &[Mapping]) -> Result<()> {
    let mut wanted = BTreeMap::new();
    for map in mapped {
        ensure(
            map.name.starts_with(r"\??\Z:\"),
            "Portable Proton requires Z: image mappings",
        )?;
        let path = decoded(&map.name);
        ensure(
            !path
                .components()
                .any(|v| v == std::path::Component::ParentDir),
            "An image mapping is outside the game directory",
        )?;
        let relative = path
            .strip_prefix(source)
            .map_err(|_| Error::other("An image mapping is outside the game directory"))?;
        let key = relative.to_string_lossy().to_lowercase();
        ensure(
            !key.is_empty()
                && wanted
                    .insert(key, (relative.to_path_buf(), map.file.as_raw_fd()))
                    .is_none(),
            "Duplicate image mapping",
        )?;
    }
    fn populate(
        original: &Path,
        destination: &Path,
        relative: &Path,
        view: &Path,
        wanted: &BTreeMap<String, (PathBuf, i32)>,
        linked: &mut BTreeSet<String>,
    ) -> Result<()> {
        let mut seen = BTreeSet::new();
        for entry in fs::read_dir(original)? {
            let entry = entry?;
            let resource = entry.path();
            if skip(&resource, view) {
                continue;
            }
            let rel = relative.join(entry.file_name());
            let key = rel.to_string_lossy().to_lowercase();
            ensure(seen.insert(key.clone()), "Ambiguous game image paths")?;
            let target = destination.join(entry.file_name());
            if let Some((_, fd)) = wanted.get(&key) {
                symlink(format!("/proc/{}/fd/{fd}", std::process::id()), target)?;
                linked.insert(key);
            } else if wanted.keys().any(|v| v.starts_with(&(key.clone() + "/"))) {
                ensure(
                    entry.file_type()?.is_dir(),
                    "Invalid mapped image directory",
                )?;
                fs::create_dir(&target)?;
                populate(&resource, &target, &rel, view, wanted, linked)?;
            } else {
                symlink(resource, target)?;
            }
        }
        for (key, (rel, _)) in wanted {
            if rel.parent() == Some(relative) {
                ensure(
                    seen.contains(key),
                    "Mapped image is missing from the game directory",
                )?;
            }
        }
        Ok(())
    }
    let mut linked = BTreeSet::new();
    populate(source, view, Path::new(""), view, &wanted, &mut linked)?;
    ensure(
        linked == wanted.keys().cloned().collect(),
        "Mapped image is missing from the game directory",
    )
}
struct Helper(Child, Duration);
impl Drop for Helper {
    fn drop(&mut self) {
        if self.0.try_wait().is_ok_and(|v| v.is_some()) {
            return;
        }
        if let Some(pid) = rustix::process::Pid::from_raw(self.0.id() as i32) {
            let _ = rustix::process::kill_process(pid, rustix::process::Signal::TERM);
        }
        let at = Instant::now();
        while at.elapsed() < self.1 {
            if self.0.try_wait().is_ok_and(|v| v.is_some()) {
                return;
            }
            std::thread::sleep(Duration::from_millis(25));
        }
        let _ = self.0.kill();
        let _ = self.0.wait();
    }
}
pub fn wine(
    root: &Path,
    args: &[OsString],
    cancel: &AtomicBool,
    last_signal: &AtomicUsize,
) -> Result<i32> {
    let root = root.canonicalize()?;
    let (game, _) = configuration(&root)?;
    let (directory, executable) = game_paths(&game);
    let argument = args
        .first()
        .and_then(|v| v.to_str())
        .ok_or_else(|| Error::other("Expected the executable path supplied by Xodus"))?;
    let source = decoded(argument).canonicalize()?;
    let game_root = root.join("games").join(directory).canonicalize()?;
    ensure(
        source.starts_with(&game_root)
            && source
                .file_name()
                .is_some_and(|v| v.to_string_lossy().eq_ignore_ascii_case(executable)),
        "The entry point does not match the configured game",
    )?;
    let map = mappings(&std::env::var("WINE_DLL_FILE_MAP").unwrap_or_default())?;
    let expected = nt(&source)?;
    let payload = map
        .iter()
        .find(|m| m.name.eq_ignore_ascii_case(&expected))
        .ok_or_else(|| Error::other("Entry point is missing from Xodus' inherited map"))?;
    let header = headers(&payload.file)?;
    let parent = source
        .parent()
        .ok_or_else(|| Error::other("Invalid entry point"))?;
    let view = View(parent.join(format!(".xodus-launch-{}", crate::py::uuid4_hex()?)));
    fs::DirBuilder::new().mode(0o700).create(&view.0)?;
    let stub = view.0.join(
        source
            .file_name()
            .ok_or_else(|| Error::other("Invalid entry point"))?,
    );
    let is_portable = std::env::var("FLIGHTDECK_PROTON_LOADER").is_ok_and(|v| v == "portable");
    if is_portable {
        portable(parent, &view.0, &map)?;
    } else {
        for entry in fs::read_dir(parent)? {
            let path = entry?.path();
            if path != source && !skip(&path, &view.0) {
                symlink(
                    &path,
                    view.0.join(
                        path.file_name()
                            .ok_or_else(|| Error::other("Invalid resource"))?,
                    ),
                )?;
            }
        }
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .open(&stub)?;
        file.write_all(&header)?;
        file.set_len(payload.file.metadata()?.len())?;
    }
    let prefix = root.join("local/msfs-prefix").canonicalize()?;
    if let Some(selected) = std::env::var_os("WINEPREFIX") {
        ensure(
            PathBuf::from(selected).canonicalize()? == prefix,
            "The Wine prefix differs from this runtime",
        )?;
    }
    let wine = std::env::var_os("XODUS_WINE_RUNNER")
        .map(PathBuf::from)
        .unwrap_or_else(|| wine_binary(&root))
        .canonicalize()?;
    let mut command = Command::new(&wine);
    command
        .arg(&stub)
        .args(&args[1..])
        .current_dir(parent)
        .env("WINEPREFIX", &prefix)
        .env("XODUS_STORE_PACKAGE_SCOPE", "FlightdeckBaseGameOnlyV1");
    if is_portable {
        command.env_remove("WINE_DLL_FILE_MAP");
    } else {
        let parent_nt = nt(parent)? + "\\";
        let view_nt = nt(&view.0)? + "\\";
        let mut names = Vec::new();
        for mapping in &map {
            names.push(format!("{}:{}", mapping.file.as_raw_fd(), mapping.name));
            if mapping
                .name
                .to_lowercase()
                .starts_with(&parent_nt.to_lowercase())
            {
                names.push(format!(
                    "{}:{}{}",
                    mapping.file.as_raw_fd(),
                    view_nt,
                    &mapping.name[parent_nt.len()..]
                ));
            }
        }
        command.env("WINE_DLL_FILE_MAP", names.join("|"));
    }
    let mut helpers = Vec::new();
    let guard = prefix.join("drive_c/windows/system32/FenixWindowGuard.exe");
    if std::env::var("WINE_FENIX_WINDOW_GUARD").is_ok_and(|v| v == "1") && guard.is_file() {
        helpers.push(Helper(
            Command::new(&wine)
                .arg(guard)
                .env("WINEPREFIX", &prefix)
                .env_remove("WINE_DLL_FILE_MAP")
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn()?,
            Duration::from_secs(5),
        ));
    }
    if std::env::var("WINE_FENIX_DISPLAY_REFRESH").is_ok_and(|v| v == "1")
        && prefix
            .join("drive_c/windows/system32/FenixMCDURefresh.exe")
            .is_file()
    {
        helpers.push(Helper(
            Command::new(std::env::current_exe()?)
                .args(["display-refresh", "--runtime"])
                .arg(&root)
                .env_remove("WINE_DLL_FILE_MAP")
                .stdin(Stdio::null())
                .spawn()?,
            Duration::from_secs(20),
        ));
    }
    let at = Instant::now();
    if !is_portable {
        for mapping in &map {
            fcntl_setfd(&mapping.file, FdFlags::empty())?;
        }
    }
    let mut child = Helper(command.spawn()?, Duration::from_secs(5));
    for mapping in &map {
        fcntl_setfd(&mapping.file, FdFlags::CLOEXEC)?;
    }
    let mut forwarded = false;
    loop {
        if let Some(status) = child.0.try_wait()? {
            let code = status
                .code()
                .unwrap_or_else(|| 128 + status.signal().unwrap_or(1));
            eprintln!(
                "xodus-wine-launch: wine_pid={} exit_code={} elapsed_seconds={:.3}",
                child.0.id(),
                code,
                at.elapsed().as_secs_f64()
            );
            drop(helpers);
            return Ok(code);
        }
        if !forwarded && cancel.load(Ordering::Relaxed) {
            if let Some(pid) = rustix::process::Pid::from_raw(child.0.id() as i32) {
                let signal = if last_signal.load(Ordering::Relaxed)
                    == signal_hook::consts::SIGINT as usize
                {
                    rustix::process::Signal::INT
                } else {
                    rustix::process::Signal::TERM
                };
                let _ = rustix::process::kill_process(pid, signal);
            }
            forwarded = true;
        }
        std::thread::sleep(Duration::from_millis(25));
    }
}
pub fn game(root: &Path) -> Result<i32> {
    let root = root.canonicalize()?;
    let (game, market) = configuration(&root)?;
    let private = root.join("private");
    ensure(
        !private.join("proton-switch.json").exists(),
        "Interrupted Proton switch. Restore Flightdeck from Proton settings first.",
    )?;
    let selected = private.join("proton-selection.json");
    let mut portable = false;
    if fs::symlink_metadata(&selected).is_ok() {
        let info = json(&selected, 65536)?;
        let runner = info["runner"]
            .as_str()
            .ok_or_else(|| Error::other("Invalid Proton runner selection"))?;
        ensure(
            matches!(info["schema"].as_u64(), Some(1 | 2))
                && regex::Regex::new(
                    r"^local/(?:proton-tests/[0-9a-f]{32}|fenix-patch-[0-9T]+-[0-9a-f]{8})/runner$",
                )
                .map_err(|_| Error::other("Invalid runner pattern"))?
                .is_match(runner)
                && root.join("runner").canonicalize()? == root.join(runner),
            "Invalid Proton runner selection",
        )?;
        portable = true;
    }
    let (directory, executable) = game_paths(&game);
    let game_root = root.join("games").join(directory);
    ensure(
        game_root.join(".xodus-streaming.msixvc").is_file() && game_root.join(executable).is_file(),
        "Game package is incomplete",
    )?;
    let mut command = Command::new(root.join("tools/xodus.sh"));
    command
        .arg("run")
        .arg(&game_root)
        .arg(root.join("tools/xodus-wine-launch"))
        .args(["--exe", executable, "--market", &market])
        .current_dir(&game_root)
        .env("WINEPREFIX", root.join("local/msfs-prefix"))
        .env("WINEARCH", "win64")
        .env("WINEESYNC", "0")
        .env("WINEFSYNC", "0")
        .env("XODUS_USER_RUNTIME", "1")
        .env("XODUS_STORE_MARKET", &market)
        .env(
            "FLIGHTDECK_PROTON_LOADER",
            if portable { "portable" } else { "native" },
        );
    command.env("WINEDEBUG","-all,err+all,warn+gdkc,fixme+gdkc,warn+mmdevapi,warn+pulse,warn+alsa,warn+xaudio2,warn+dsound,warn+winegstreamer");
    for (key, value) in [("DXVK_LOG_LEVEL", "warn"), ("VKD3D_DEBUG", "warn")] {
        if std::env::var_os(key).is_none() {
            command.env(key, value);
        }
    }
    let previous = std::env::var("WINEDLLOVERRIDES").unwrap_or_default();
    command.env(
        "WINEDLLOVERRIDES",
        format!(
            "{}{}xgameruntime=n;xgameruntime_original=n,b;xodus_store_test=b",
            previous,
            if previous.is_empty() { "" } else { ";" }
        ),
    );
    let previous = std::env::var("WINEDLLPATH").unwrap_or_default();
    command.env(
        "WINEDLLPATH",
        format!(
            "{}{}{}",
            root.join("local/store-runtime").display(),
            if previous.is_empty() { "" } else { ":" },
            previous
        ),
    );
    let marker = private.join("fenix-linux-patch.json");
    if fs::symlink_metadata(&marker).is_ok() {
        ensure(
            json(&marker, 1024 * 1024)?["state"] == "installed",
            "Fenix setup is incomplete. Restore or finish it before starting MSFS.",
        )?;
        for (key, value) in [
            (
                "WINE_TRACK_WRITECOPY",
                "apps:Fenix.exe,FenixSystem.exe,FenixDisplay.exe,FenixCDU.exe,FlightSimulator2024.exe",
            ),
            ("WINE_D2D1_DISPLAY_EFFECTS", "FenixDisplay.exe;FenixCDU.exe"),
            ("WINE_D2D1_GEOMETRY_PROVIDER", "FenixDisplay.exe"),
            (
                "WINE_DWRITE_UNHINTED_OUTLINES",
                "FenixDisplay.exe;FenixCDU.exe",
            ),
            ("DOTNET_SYSTEM_GLOBALIZATION_USENLS", "1"),
            ("DOTNET_ReadyToRun", "0"),
            ("PROTON_NO_NTSYNC", "1"),
            ("WINE_FENIX_WINDOW_GUARD", "1"),
            ("WINE_FENIX_HELPER_WINDOWS", "1"),
            ("WINE_FENIX_DISPLAY_REFRESH", "1"),
        ] {
            command.env(key, value);
        }
    }
    command.env("XODUS_WINE_RUNNER", wine_binary(&root));
    if portable {
        command
            .env("WINE_DISABLE_FAST_SYNC", "1")
            .env("WINELOADER", wine_binary(&root))
            .env("WINESERVER", root.join("runner/files/bin/wineserver"));
    }
    command
        .env(
            "MEDIACONV_BLANK_VIDEO_FILE",
            root.join("runner/files/share/media/blank.mkv"),
        )
        .env(
            "MEDIACONV_BLANK_AUDIO_FILE",
            root.join("runner/files/share/media/blank.ptna"),
        );
    if root.join("local/media-plugins").is_dir() {
        let previous = std::env::var("GST_PLUGIN_PATH_1_0").unwrap_or_default();
        command.env(
            "GST_PLUGIN_PATH_1_0",
            format!(
                "{}{}{}",
                root.join("local/media-plugins").display(),
                if previous.is_empty() { "" } else { ":" },
                previous
            ),
        );
    }
    fs::create_dir_all(private.join("gstreamer"))?;
    command
        .env("WINE_GST_REGISTRY_DIR", private.join("gstreamer"))
        .env("GST_REGISTRY_1_0", private.join("gstreamer/registry.bin"));
    if private.join("local-saves.enabled").is_file() && private.join("local-saves").is_dir() {
        command.env("XODUS_LOCAL_GAMESAVE", "1").env(
            "XODUS_LOCAL_GAMESAVE_ROOT",
            format!(
                "Z:{}\\private\\local-saves",
                root.to_string_lossy().replace('/', "\\")
            ),
        );
    } else {
        command
            .env_remove("XODUS_LOCAL_GAMESAVE")
            .env_remove("XODUS_LOCAL_GAMESAVE_ROOT");
    }
    Err(command.exec().into())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn malformed_pe_and_descriptor_maps_fail_closed() {
        let t = tempfile::tempdir().expect("fixture");
        let p = t.path().join("image");
        fs::write(&p, b"not executable").expect("file");
        assert!(headers(&File::open(p).expect("open")).is_err());
        for value in ["", "secret", "-1:foo", "999999999999999999:foo"] {
            assert!(mappings(value).is_err());
        }
    }
    #[test]
    fn portable_mapping_refuses_missing_and_escaping_images() {
        let t = tempfile::tempdir().expect("fixture");
        let source = t.path().join("game");
        let view = source.join(".xodus-launch-test");
        fs::create_dir_all(&view).expect("view");
        let image = source.join("image.exe");
        fs::write(&image, b"fixture").expect("image");
        let mapping = |name| Mapping {
            file: File::open(&image).expect("file"),
            name,
        };
        assert!(
            portable(
                &source,
                &view,
                &[mapping(nt(&source.join("missing.exe")).expect("nt"))]
            )
            .is_err()
        );
        assert!(
            portable(
                &source,
                &view,
                &[mapping(nt(&t.path().join("outside.exe")).expect("nt"))]
            )
            .is_err()
        );
        assert_eq!(fs::read(image).expect("preserved"), b"fixture");
    }
}
