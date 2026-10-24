// SPDX-License-Identifier: MIT
//! One MCDU refresh per owned service process, with durable preference recovery.
use super::{atomic_json, ensure, json, wine_binary};
use crate::{Error, Result};
use serde_json::{Value, json as value};
use std::{
    collections::{BTreeMap, BTreeSet},
    fs::{self, File, OpenOptions},
    io::Read,
    os::unix::{ffi::OsStrExt, fs::OpenOptionsExt},
    path::{Path, PathBuf},
    process::{Command, Stdio},
    sync::atomic::{AtomicBool, Ordering},
    time::{Duration, Instant},
};
const SERVICES: [&str; 5] = [
    "fenixdisplay.exe",
    "fenixsystem.exe",
    "fenixcdu.exe",
    "fenix.exe",
    "fenix.gqlgateway.exe",
];
const QUERY: &str = r#"{dataRef{home:dataRef(name:"fenix.controls.homeCockpit"){value}left:dataRef(name:"aircraft.mcdu1.display"){value}right:dataRef(name:"aircraft.mcdu2.display"){value}}}"#;
type Identity = (u32, String);
type Services = BTreeMap<String, Identity>;
fn identity(proc: &Path) -> Result<Identity> {
    let text = fs::read_to_string(proc.join("stat"))?;
    let born = text
        .rsplit_once(')')
        .and_then(|(_, v)| v.split_whitespace().nth(19))
        .ok_or_else(|| Error::other("Invalid service identity"))?;
    let pid = proc
        .file_name()
        .and_then(|v| v.to_str())
        .and_then(|v| v.parse().ok())
        .ok_or_else(|| Error::other("Invalid service PID"))?;
    Ok((pid, born.into()))
}
fn services_at(prefix: &Path, proc_root: &Path) -> Result<Services> {
    let mut result = BTreeMap::new();
    for entry in fs::read_dir(proc_root)?.take(1_000_000) {
        let path = entry?.path();
        if !path
            .file_name()
            .is_some_and(|v| v.as_bytes().iter().all(u8::is_ascii_digit))
        {
            continue;
        }
        let found = (|| -> Result<Option<(String, Identity)>> {
            let args = fs::read(path.join("cmdline"))?;
            let name = String::from_utf8_lossy(args.split(|b| *b == 0).next().unwrap_or_default())
                .replace('\\', "/")
                .rsplit('/')
                .next()
                .unwrap_or("")
                .to_ascii_lowercase();
            if !SERVICES.contains(&name.as_str()) {
                return Ok(None);
            }
            let expected = [b"WINEPREFIX=".as_slice(), prefix.as_os_str().as_bytes()].concat();
            let env = fs::read(path.join("environ"))?;
            if !env.split(|b| *b == 0).any(|v| v == expected) {
                return Ok(None);
            }
            Ok(Some((name, identity(&path)?)))
        })();
        if let Ok(Some((name, id))) = found
            && result.insert(name, id).is_some()
        {
            return Ok(BTreeMap::new());
        }
    }
    Ok(result)
}
fn services(prefix: &Path) -> Services {
    services_at(prefix, Path::new("/proc")).unwrap_or_default()
}
fn owns_api_at(services: &Services, proc_root: &Path) -> bool {
    (|| -> Result<bool> {
        let Some(id) = services.get("fenix.gqlgateway.exe") else {
            return Ok(false);
        };
        let proc = proc_root.join(id.0.to_string());
        if identity(&proc)? != *id {
            return Ok(false);
        }
        let sockets: BTreeSet<_> = fs::read_dir(proc.join("fd"))?
            .take(65536)
            .filter_map(|v| v.ok().and_then(|e| fs::read_link(e.path()).ok()))
            .collect();
        let raw = fs::read_to_string(proc.join("net/tcp"))?;
        for row in raw
            .lines()
            .skip(1)
            .map(|v| v.split_whitespace().collect::<Vec<_>>())
        {
            if row.len() > 9
                && ["00000000:1F93", "0100007F:1F93"].contains(&row[1])
                && row[3] == "0A"
                && sockets.contains(&PathBuf::from(format!("socket:[{}]", row[9])))
            {
                return Ok(identity(&proc)? == *id);
            }
        }
        Ok(false)
    })()
    .unwrap_or(false)
}
fn owns_api(services: &Services) -> bool {
    owns_api_at(services, Path::new("/proc"))
}
trait Control {
    fn query(&self) -> Result<Value>;
    fn home(&self, value: bool) -> Result<()>;
}
struct Api {
    agent: ureq::Agent,
    prefix: PathBuf,
}
impl Api {
    fn request(&self, query: &str) -> Result<Value> {
        ensure(
            owns_api(&services(&self.prefix)),
            "Fenix API ownership changed",
        )?;
        let body = value!({"query":query}).to_string();
        let mut response = self
            .agent
            .post("http://127.0.0.1:8083/graphql")
            .header("Content-Type", "application/json")
            .send(body.as_bytes())
            .map_err(|_| Error::other("Fenix API unavailable"))?;
        ensure(
            response.status().as_u16() == 200,
            "Fenix API redirect rejected",
        )?;
        let mut bytes = Vec::new();
        response
            .body_mut()
            .as_reader()
            .take(65537)
            .read_to_end(&mut bytes)?;
        ensure(bytes.len() <= 65536, "Fenix API response too large")?;
        let result: Value = serde_json::from_slice(&bytes)
            .map_err(|_| Error::other("Invalid Fenix API response"))?;
        ensure(
            (result["errors"].is_null() || result["errors"].as_array().is_some_and(Vec::is_empty))
                && result["data"]["dataRef"].is_object(),
            "Fenix API unavailable",
        )?;
        Ok(result["data"]["dataRef"].clone())
    }
}
impl Control for Api {
    fn query(&self) -> Result<Value> {
        self.request(QUERY)
    }
    fn home(&self, value: bool) -> Result<()> {
        let result = self.request(&format!(
            "mutation{{dataRef{{writeBool(name:\"fenix.controls.homeCockpit\",value:{value})}}}}"
        ))?;
        ensure(
            result["writeBool"] == true,
            "Fenix display preference was not accepted",
        )
    }
}
fn recover(api: &impl Control, journal: &Path) -> Result<()> {
    if fs::symlink_metadata(journal).is_err() {
        return Ok(());
    }
    let saved = json(journal, 1024)?;
    ensure(
        saved["format"].as_u64() == Some(1),
        "Invalid display refresh journal",
    )?;
    let original = saved["home"]
        .as_bool()
        .ok_or_else(|| Error::other("Invalid display refresh journal"))?;
    api.home(original)?;
    ensure(
        api.query()?["home"]["value"] == original,
        "Display preference restoration pending",
    )?;
    fs::remove_file(journal)?;
    File::open(
        journal
            .parent()
            .ok_or_else(|| Error::other("Invalid journal"))?,
    )?
    .sync_all()?;
    Ok(())
}
fn transaction(
    api: &impl Control,
    journal: &Path,
    cancel: &AtomicBool,
    mut run: impl FnMut(&str) -> Result<()>,
    mut delay: impl FnMut(),
) -> Result<bool> {
    let state = api.query()?;
    let original = state["home"]["value"]
        .as_bool()
        .ok_or_else(|| Error::other("MCDU display data not ready"))?;
    ensure(
        ["left", "right"].iter().all(|v| {
            state[v]["value"]
                .as_str()
                .is_some_and(|v| v.contains("<root>"))
        }),
        "MCDU display data not ready",
    )?;
    run("--probe")?;
    if cancel.load(Ordering::Relaxed) {
        return Ok(false);
    }
    atomic_json(journal, &value!({"format":1,"home":original}))?;
    let result = (|| {
        api.home(!original)?;
        delay();
        if original {
            api.home(true)?;
            delay();
        }
        run("--refresh")?;
        Ok(true)
    })();
    let recovery = recover(api, journal);
    recovery?;
    result
}
pub fn run(root: &Path, cancel: &AtomicBool) -> Result<()> {
    let root = root.canonicalize()?;
    if json(&root.join("private/runtime.json"), 65536)?["game_id"]
        .as_str()
        .is_some_and(|v| v != "msfs2024")
    {
        return Ok(());
    }
    let lease = OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .custom_flags(rustix::fs::OFlags::NOFOLLOW.bits() as i32)
        .open(root.join("private/fenix-display-refresh.lock"))?;
    match rustix::fs::flock(&lease, rustix::fs::FlockOperation::NonBlockingLockExclusive) {
        Ok(()) => {}
        Err(rustix::io::Errno::WOULDBLOCK) => return Ok(()),
        Err(e) => return Err(e.into()),
    }
    let api = Api {
        prefix: root.join("local/msfs-prefix"),
        agent: ureq::Agent::new_with_config(
            ureq::Agent::config_builder()
                .proxy(None)
                .max_redirects(0)
                .timeout_global(Some(Duration::from_secs(2)))
                .build(),
        ),
    };
    let journal = root.join("private/fenix-display-refresh.json");
    let helper = api
        .prefix
        .join("drive_c/windows/system32/FenixMCDURefresh.exe");
    let library = root.join("games/MSFS2024/SimConnect_internal.dll");
    let mut seen = None;
    let mut completed = None;
    let mut since = Instant::now();
    let mut attempts = 0;
    while !cancel.load(Ordering::Relaxed) {
        for _ in 0..10 {
            if cancel.load(Ordering::Relaxed) {
                break;
            }
            std::thread::sleep(Duration::from_millis(100));
        }
        if cancel.load(Ordering::Relaxed) {
            break;
        }
        let owned = services(&api.prefix);
        let display = owned.get("fenixdisplay.exe").cloned();
        if owned.len() != 5 || display.is_none() || !owns_api(&owned) {
            seen = None;
            since = Instant::now();
            continue;
        }
        if display != seen {
            seen = display.clone();
            since = Instant::now();
            attempts = 0;
        }
        if fs::symlink_metadata(&journal).is_ok() && recover(&api, &journal).is_err() {
            continue;
        }
        if display == completed || attempts >= 3 || since.elapsed() < Duration::from_secs(8) {
            continue;
        }
        let result = (|| {
            ensure(
                services(&api.prefix) == owned && owns_api(&owned),
                "Fenix process changed",
            )?;
            ensure(
                helper.is_file() && library.is_file(),
                "Installed display refresh dependency unavailable",
            )?;
            transaction(
                &api,
                &journal,
                cancel,
                |mode| {
                    ensure(
                        services(&api.prefix) == owned && owns_api(&owned),
                        "Fenix process changed",
                    )?;
                    let mut command = Command::new(wine_binary(&root));
                    command
                        .arg(&helper)
                        .arg(mode)
                        .arg(format!(
                            "Z:{}",
                            library.to_string_lossy().replace('/', "\\")
                        ))
                        .current_dir(
                            helper
                                .parent()
                                .ok_or_else(|| Error::other("Invalid helper"))?,
                        )
                        .env("WINEPREFIX", &api.prefix)
                        .env("WINEDEBUG", "-all")
                        .stdin(Stdio::null())
                        .stdout(Stdio::null())
                        .stderr(Stdio::null());
                    for key in [
                        "WINE_DLL_FILE_MAP",
                        "WINESERVERSOCKET",
                        "WINEPRELOADRESERVE",
                        "WINELOADERNOEXEC",
                        "WINELOADER",
                        "WINEDLLPATH",
                    ] {
                        command.env_remove(key);
                    }
                    let mut child = command.spawn()?;
                    let at = Instant::now();
                    loop {
                        if let Some(code) = child.try_wait()? {
                            return ensure(code.success(), "MCDU brightness refresh unavailable");
                        }
                        if at.elapsed() > Duration::from_secs(15) {
                            let _ = child.kill();
                            let _ = child.wait();
                            return Err(Error::other("MCDU brightness refresh timed out"));
                        }
                        std::thread::sleep(Duration::from_millis(25));
                    }
                },
                || std::thread::sleep(Duration::from_millis(350)),
            )
        })();
        match result {
            Ok(true) => {
                completed = display;
                println!("Fenix: MCDU startup image refreshed; display preference restored.");
            }
            Ok(false) => {}
            Err(_) => {
                attempts += 1;
                since = Instant::now();
                println!("Fenix: display refresh deferred; waiting for local display services.");
            }
        }
    }
    if owns_api(&services(&api.prefix)) {
        let _ = recover(&api, &journal);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::{Cell, RefCell};
    #[test]
    fn process_identity_prefix_and_listener_ownership_must_all_match() {
        let temp = tempfile::tempdir().expect("proc fixture");
        let prefix = temp.path().join("prefix");
        let proc_root = temp.path().join("proc");
        let process = proc_root.join("10");
        fs::create_dir_all(process.join("fd")).expect("fd directory");
        fs::create_dir_all(process.join("net")).expect("network directory");
        fs::write(
            process.join("stat"),
            format!("10 (gateway) S {}33\n", "0 ".repeat(18)),
        )
        .expect("identity");
        fs::write(process.join("cmdline"), b"C:\\Fenix.GqlGateway.exe\0").expect("command");
        fs::write(
            process.join("environ"),
            format!("WINEPREFIX={}\0", prefix.display()),
        )
        .expect("prefix");
        std::os::unix::fs::symlink("socket:[42]", process.join("fd/1")).expect("socket");
        fs::write(
            process.join("net/tcp"),
            "header\n0: 0100007F:1F93 00000000:0000 0A 0 0 0 0 0 42\n",
        )
        .expect("listener");
        let owned = services_at(&prefix, &proc_root).expect("services");
        assert_eq!(owned.len(), 1);
        assert!(owns_api_at(&owned, &proc_root));
        assert!(
            services_at(&temp.path().join("other-profile"), &proc_root)
                .expect("foreign prefix")
                .is_empty()
        );
        fs::write(
            process.join("stat"),
            format!("10 (gateway) S {}34\n", "0 ".repeat(18)),
        )
        .expect("reused PID");
        assert!(!owns_api_at(&owned, &proc_root));
        fs::write(
            process.join("stat"),
            format!("10 (gateway) S {}33\n", "0 ".repeat(18)),
        )
        .expect("identity");
        fs::remove_file(process.join("fd/1")).expect("foreign listener");
        assert!(!owns_api_at(&owned, &proc_root));
    }
    struct Fake {
        home: Cell<bool>,
        writes: RefCell<Vec<bool>>,
        offline: Cell<bool>,
        confirm: Cell<bool>,
    }
    impl Fake {
        fn new(home: bool) -> Self {
            Self {
                home: Cell::new(home),
                writes: RefCell::new(Vec::new()),
                offline: Cell::new(false),
                confirm: Cell::new(true),
            }
        }
    }
    impl Control for Fake {
        fn query(&self) -> Result<Value> {
            Ok(
                value!({"home":{"value":self.home.get()},"left":{"value":"<root>left</root>"},"right":{"value":"<root>right</root>"}}),
            )
        }
        fn home(&self, v: bool) -> Result<()> {
            ensure(!self.offline.get(), "Offline")?;
            self.writes.borrow_mut().push(v);
            if self.confirm.get() {
                self.home.set(v);
            }
            Ok(())
        }
    }
    #[test]
    fn preference_and_pages_survive_both_modes() {
        for original in [false, true] {
            let t = tempfile::tempdir().expect("fixture");
            let p = t.path().join("journal.json");
            let api = Fake::new(original);
            let mut modes = Vec::new();
            assert!(
                transaction(
                    &api,
                    &p,
                    &AtomicBool::new(false),
                    |v| {
                        modes.push(v.to_owned());
                        Ok(())
                    },
                    || {}
                )
                .expect("refresh")
            );
            assert_eq!(api.home.get(), original);
            assert_eq!(modes, ["--probe", "--refresh"]);
            assert!(!p.exists());
            assert_eq!(
                *api.writes.borrow(),
                if original {
                    vec![false, true, true]
                } else {
                    vec![true, false]
                }
            );
        }
    }
    #[test]
    fn probe_failure_and_cancellation_leave_preferences_untouched() {
        for cancel in [false, true] {
            let t = tempfile::tempdir().expect("fixture");
            let p = t.path().join("journal.json");
            let api = Fake::new(false);
            let r = transaction(
                &api,
                &p,
                &AtomicBool::new(cancel),
                |_| {
                    if cancel {
                        Ok(())
                    } else {
                        Err(Error::other("Probe failed"))
                    }
                },
                || {},
            );
            assert!(r.is_err() || r == Ok(false));
            assert!(api.writes.borrow().is_empty());
            assert!(!p.exists());
        }
    }
    #[test]
    fn failed_refresh_restores_and_uncertain_restore_keeps_journal() {
        let t = tempfile::tempdir().expect("fixture");
        let p = t.path().join("journal.json");
        let api = Fake::new(false);
        assert!(
            transaction(
                &api,
                &p,
                &AtomicBool::new(false),
                |v| ensure(v == "--probe", "Failure"),
                || {}
            )
            .is_err()
        );
        assert!(!api.home.get());
        assert!(!p.exists());
        atomic_json(&p, &value!({"format":1,"home":false})).expect("journal");
        api.home.set(true);
        api.offline.set(true);
        assert!(recover(&api, &p).is_err());
        assert!(p.exists());
        api.offline.set(false);
        recover(&api, &p).expect("recover");
        assert!(!api.home.get());
        assert!(!p.exists());
    }
    #[test]
    fn invalid_and_linked_journals_are_rejected() {
        let t = tempfile::tempdir().expect("fixture");
        let p = t.path().join("journal.json");
        let api = Fake::new(false);
        fs::write(&p, r#"{"format":1,"home":"false"}"#).expect("fixture");
        assert!(recover(&api, &p).is_err());
        fs::remove_file(&p).expect("remove");
        let target = t.path().join("untouched");
        fs::write(&target, b"keep").expect("target");
        std::os::unix::fs::symlink(&target, &p).expect("link");
        assert!(recover(&api, &p).is_err());
        assert_eq!(fs::read(target).expect("preserved"), b"keep");
    }
}
