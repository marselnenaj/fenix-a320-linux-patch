// SPDX-License-Identifier: MIT
//! Developer-only CLR repair probe; accepts only a marked isolated runtime.
use fenix_patch::{clr_loader, core::RealWine, fsx, json::json, system::Host};
use std::{fs::File, path::PathBuf};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let root = PathBuf::from(
        std::env::args_os()
            .nth(1)
            .ok_or("Missing isolated runtime")?,
    )
    .canonicalize()?;
    if fsx::read(&root.join("private/synthetic-probe"))? != b"Flightdeck isolated test\n" {
        return Err("This probe requires a new marked, account-free profile".into());
    }
    let host = Host::new(root.clone());
    let log = File::create(root.join("private/standalone-clr.log"))?;
    let wine = RealWine::new(
        &host,
        &root.join("local/msfs-prefix"),
        &root.join("runner"),
        &log,
    );
    let repaired = clr_loader::prepare(&host, &wine)?;
    println!("{}", json!({"schema":1,"repaired":repaired}));
    Ok(())
}
