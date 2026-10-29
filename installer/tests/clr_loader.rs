// SPDX-License-Identifier: MIT
#![allow(clippy::unwrap_used)]
use fenix_patch::{clr_loader, core::RealWine, fsx, json::Value, system::Host};
use std::{fs, os::unix::fs::PermissionsExt};

#[test]
fn native_only_loader_settings_are_backed_up_and_repaired_once() {
    for value in ["native", "n", "builtin", "", "native,builtin"] {
        let temp = tempfile::tempdir().unwrap();
        let prefix = temp.path().join("prefix");
        let runner = temp.path().join("runner");
        fs::create_dir_all(&prefix).unwrap();
        fs::create_dir_all(runner.join("files/bin")).unwrap();
        fs::write(prefix.join("override"), value).unwrap();
        let executable = runner.join("files/bin/wine");
        fs::write(&executable, b"#!/bin/sh\nif [ \"$2\" = query ]; then\n read -r value < \"$WINEPREFIX/override\" || true\n printf '    mscoree    REG_SZ    %s\\n' \"$value\"\nelif [ \"$2\" = add ]; then\n printf '%s' \"$9\" > \"$WINEPREFIX/override\"\nfi\n").unwrap();
        fs::set_permissions(&executable, fs::Permissions::from_mode(0o700)).unwrap();
        let host = Host::new(temp.path().into());
        let log = fs::File::create(temp.path().join("wine.log")).unwrap();
        let wine = RealWine::new(&host, &prefix, &runner, &log);
        let migrated = clr_loader::prepare(&host, &wine).unwrap();
        assert_eq!(migrated, ["native", "n"].contains(&value));
        assert!(!clr_loader::prepare(&host, &wine).unwrap());
        let backup = prefix.join(".fenix-clr-loader.json");
        if migrated {
            let state: Value = fsx::read_json(&backup).unwrap();
            assert_eq!(state["changes"].as_array().unwrap().len(), 1);
            assert_eq!(state["changes"][0]["before"], value);
            assert_eq!(
                fs::metadata(&backup).unwrap().permissions().mode() & 0o777,
                0o600
            );
            assert_eq!(
                fs::read_to_string(prefix.join("override")).unwrap(),
                "native,builtin"
            );
            fs::write(prefix.join("override"), "native").unwrap();
            fs::write(&backup, "invalid backup").unwrap();
            assert!(clr_loader::prepare(&host, &wine).is_err());
            assert_eq!(
                fs::read_to_string(prefix.join("override")).unwrap(),
                "native"
            );
        } else {
            assert!(!backup.exists());
        }
    }
}

#[test]
fn unknown_types_duplicate_values_and_explicit_policies_survive() {
    for value in ["native", "NATIVE", "n"] {
        assert_eq!(
            clr_loader::native_only(&format!("mscoree REG_SZ {value}\n")),
            Some(value)
        );
    }
    for output in [
        "other REG_SZ native\n",
        "mscoree REG_EXPAND_SZ native\n",
        "mscoree REG_SZ native\nmscoree REG_SZ native\n",
        "mscoree REG_SZ builtin\n",
        "mscoree REG_SZ native,builtin\n",
        "mscoree REG_SZ \n",
    ] {
        assert!(clr_loader::native_only(output).is_none());
    }
}
