// SPDX-License-Identifier: MIT
//! Preserve native CLR priority without disabling Wine's IL-only assembly loader.
use crate::{
    Error, Result, argv,
    core::{Wine, wine_binary},
    fsx::{read_json, regular, write_json},
    json::{Value, json},
    process::{self, Cmd, Input, Output},
    system::System,
};

pub const MSCOREE_OVERRIDE: &str = "native,builtin";
const KEY: &str = r"HKCU\Software\Wine\DllOverrides";

/// Only an unambiguous native-only value is eligible for migration.
pub fn native_only(output: &str) -> Option<&str> {
    let values: Vec<_> = output
        .lines()
        .filter_map(|line| {
            let (name, rest) = line.trim_start().split_once(char::is_whitespace)?;
            if !name.eq_ignore_ascii_case("mscoree") {
                return None;
            }
            let (kind, value) = rest.trim_start().split_once(char::is_whitespace)?;
            Some((kind, value.trim()))
        })
        .collect();
    match values.as_slice() {
        [("REG_SZ", value)]
            if value.eq_ignore_ascii_case("native") || value.eq_ignore_ascii_case("n") =>
        {
            Some(*value)
        }
        _ => None,
    }
}

/// Caller owns the profile lock. Use Wine's registry service, retaining a backup
/// before changing a value; never replace a DLL or touch per-application choices.
pub fn prepare(system: &dyn System, wine: &dyn Wine) -> Result<bool> {
    let mut cmd = Cmd::new(argv![
        wine_binary(wine.runner()),
        "reg",
        "query",
        KEY,
        "/v",
        "mscoree"
    ]);
    cmd.env = Some(wine.env());
    cmd.cwd = Some(wine.prefix());
    cmd.stdin = Input::Null;
    cmd.output = Output::Capture;
    cmd.timeout = Some(30);
    let result = process::run(&cmd, &|| system.interrupted())?;
    if result.code != 0 {
        return Ok(false);
    }
    if result.stdout.len() > 16384 {
        return Err(Error::patch("CLR registry response is too large."));
    }
    let output = String::from_utf8_lossy(&result.stdout);
    let Some(before) = native_only(&output) else {
        return Ok(false);
    };
    let path = wine.prefix().join(".fenix-clr-loader.json");
    let mut backup: Value = if path.symlink_metadata().is_ok() {
        read_json(regular(&path, Some(65536))?)?
    } else {
        json!({"schema":1,"changes":[]})
    };
    if backup["schema"] != 1 || !backup["changes"].as_array().is_some_and(|v| v.len() < 32) {
        return Err(Error::patch(
            "The saved CLR loader settings could not be verified.",
        ));
    }
    backup["changes"].as_array_mut().ok_or_else(|| Error::patch("Invalid CLR loader backup."))?
        .push(json!({"key":KEY,"name":"mscoree","kind":"REG_SZ","before":before,"after":MSCOREE_OVERRIDE}));
    write_json(&path, &backup)?;
    wine.reg(KEY, "mscoree", MSCOREE_OVERRIDE, "REG_SZ")?;
    Ok(true)
}
