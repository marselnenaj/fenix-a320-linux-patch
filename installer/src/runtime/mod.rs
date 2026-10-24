// SPDX-License-Identifier: MIT
//! Native replacements for the historical Python launch helpers.
pub mod display;
pub mod launch;
use crate::{Error, Result};
use serde_json::Value;
use std::{
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    os::unix::fs::{OpenOptionsExt, PermissionsExt},
    path::Path,
};
pub(super) fn ensure(value: bool, message: &str) -> Result<()> {
    if value {
        Ok(())
    } else {
        Err(Error::other(message))
    }
}
pub(super) fn read(path: &Path, limit: u64) -> Result<Vec<u8>> {
    let mut file = OpenOptions::new()
        .read(true)
        .custom_flags(rustix::fs::OFlags::NOFOLLOW.bits() as i32)
        .open(path)?;
    ensure(
        file.metadata()?.is_file() && file.metadata()?.len() <= limit,
        "Invalid runtime file",
    )?;
    let mut bytes = Vec::new();
    Read::by_ref(&mut file)
        .take(limit + 1)
        .read_to_end(&mut bytes)?;
    ensure(
        bytes.len() as u64 <= limit,
        "Runtime file exceeds its size limit",
    )?;
    Ok(bytes)
}
pub(super) fn json(path: &Path, limit: u64) -> Result<Value> {
    serde_json::from_slice(&read(path, limit)?).map_err(|_| Error::other("Invalid runtime JSON"))
}
pub(super) fn atomic_json(path: &Path, value: &Value) -> Result<()> {
    let parent = path
        .parent()
        .ok_or_else(|| Error::other("Invalid journal path"))?;
    let temporary = parent.join(format!(".fenix-journal-{}", crate::py::uuid4_hex()?));
    let result = (|| {
        let mut file = OpenOptions::new()
            .write(true)
            .create_new(true)
            .mode(0o600)
            .open(&temporary)?;
        file.write_all(value.to_string().as_bytes())?;
        file.sync_all()?;
        fs::rename(&temporary, path)?;
        File::open(parent)?.sync_all()?;
        Ok(())
    })();
    if temporary.exists() {
        let _ = fs::remove_file(temporary);
    }
    result
}
pub(super) fn executable(path: &Path) -> bool {
    fs::metadata(path).is_ok_and(|m| m.is_file() && m.permissions().mode() & 0o111 != 0)
}
pub(super) fn wine_binary(root: &Path) -> std::path::PathBuf {
    let directory = root.join("runner/files/bin");
    let wine64 = directory.join("wine64");
    if executable(&wine64) {
        wine64
    } else {
        directory.join("wine")
    }
}
