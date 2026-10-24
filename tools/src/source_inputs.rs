// SPDX-License-Identifier: MIT
//! Restore only checksum-pinned source members from an earlier source release.
use crate::{Context, build::read_lock};
use fenix_patch::{
    Error, Result, fsx,
    json::{self, Dict, Value},
};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File},
    io::Read,
    path::Path,
};
pub fn restore(ctx: &Context<'_>, archive: &Path, release: &str) -> Result<()> {
    if release.is_empty()
        || !release
            .bytes()
            .all(|v| v.is_ascii_alphanumeric() || b".-".contains(&v))
    {
        return Err(Error::other("Invalid source release version"));
    }
    let lock = Value::Object(read_lock(ctx.root())?);
    let variants = lock.table("variants")?;
    let mut wanted = BTreeMap::new();
    for entry in std::iter::once(&lock).chain(variants.values()) {
        if let Some(dxvk) = entry.get("dxvk") {
            let name = dxvk.need_str("source")?;
            if Path::new(name).file_name() != Some(std::ffi::OsStr::new(name)) {
                return Err(Error::other("Invalid source archive name"));
            }
            let digest = entry.need("sources")?.need_str(name)?;
            if let Some(old) = wanted.insert(name.to_owned(), digest.to_owned())
                && old != digest
            {
                return Err(Error::other("Conflicting source pins"));
            }
        }
    }
    let mut found = BTreeSet::new();
    let decoder = flate2::read::GzDecoder::new(File::open(archive)?);
    let mut tar = tar::Archive::new(decoder);
    for item in tar.entries()? {
        let mut entry = item?;
        let path = entry.path()?.into_owned();
        for (name, expected) in &wanted {
            let selected = format!("fenix-a320-linux-patch-{release}/sources/{name}");
            if path != Path::new(&selected) {
                continue;
            }
            if !entry.header().entry_type().is_file()
                || !found.insert(name.clone())
                || entry.size() > 64 * 1024 * 1024
            {
                return Err(Error::other("Invalid source archive member"));
            }
            let mut bytes = Vec::new();
            entry
                .by_ref()
                .take(64 * 1024 * 1024 + 1)
                .read_to_end(&mut bytes)?;
            if !json::is_text(&Value::String(expected.clone()), &fsx::digest_bytes(&bytes)) {
                return Err(Error::other("Source checksum mismatch"));
            }
            let folder = ctx.root().join("sources");
            fs::create_dir_all(&folder)?;
            fsx::atomic(&folder.join(name), &bytes, 0o644)?;
        }
    }
    if found.len() != wanted.len() {
        return Err(Error::other(
            "Required corresponding source archive is missing",
        ));
    }
    ctx.print(&format!(
        "Restored {} checksum-verified source archives",
        found.len()
    ))
}
