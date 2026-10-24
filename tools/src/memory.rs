// SPDX-License-Identifier: MIT
//! Aggregate counters only: never read process arguments, environment or memory.
use fenix_patch::{Error, Result, py};
use std::{
    collections::BTreeMap,
    fs::{self, OpenOptions},
    io::Write,
    path::Path,
    time::{Duration, Instant},
};

pub fn counters(text: &str) -> BTreeMap<String, u64> {
    text.lines()
        .filter_map(|line| {
            let (key, value) = line.split_once(':')?;
            let words: Vec<_> = value.split_whitespace().collect();
            if words.len() == 2 && words[1] == "kB" {
                words[0].parse().ok().map(|v| (key.to_owned(), v))
            } else {
                None
            }
        })
        .collect()
}
fn identity(proc: &Path) -> Result<String> {
    fs::read_to_string(proc.join("stat"))?
        .rsplit_once(')')
        .and_then(|(_, rest)| rest.split_whitespace().nth(19))
        .map(str::to_owned)
        .ok_or_else(|| Error::other("Invalid process identity"))
}
pub fn run(pid: u32, output: &Path, interval: f64, samples: u32) -> Result<()> {
    if pid == 0 || samples == 0 || !interval.is_finite() || interval <= 0.0 || interval > 86_400.0 {
        return Err(Error::other(
            "PID, interval and sample count must be positive finite values; interval must not exceed one day",
        ));
    }
    let proc = std::path::PathBuf::from(format!("/proc/{pid}"));
    let initial = identity(&proc)?;
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(output)?;
    writeln!(
        file,
        "timestamp_utc,elapsed_s,pid,rss_kib,pss_kib,rss_anon_kib,rss_file_kib,rss_shmem_kib,private_clean_kib,private_dirty_kib,swap_kib"
    )?;
    let started = Instant::now();
    for sample in 0..samples {
        if identity(&proc)? != initial {
            return Err(Error::other(
                "PID was reused; sampling stopped. Partial CSV retained.",
            ));
        }
        let status = counters(&fs::read_to_string(proc.join("status"))?);
        let rollup = counters(&fs::read_to_string(proc.join("smaps_rollup"))?);
        if identity(&proc)? != initial {
            return Err(Error::other(
                "PID changed while reading counters. Partial CSV retained.",
            ));
        }
        let now = py::Utc::now();
        write!(
            file,
            "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}+00:00,{:.3},{pid}",
            now.year,
            now.month,
            now.day,
            now.hour,
            now.minute,
            now.second,
            started.elapsed().as_secs_f64()
        )?;
        for (values, key) in [
            (&rollup, "Rss"),
            (&rollup, "Pss"),
            (&status, "RssAnon"),
            (&status, "RssFile"),
            (&status, "RssShmem"),
            (&rollup, "Private_Clean"),
            (&rollup, "Private_Dirty"),
            (&rollup, "Swap"),
        ] {
            write!(
                file,
                ",{}",
                values.get(key).map(u64::to_string).unwrap_or_default()
            )?;
        }
        writeln!(file)?;
        file.flush()?;
        if sample + 1 < samples {
            std::thread::sleep(
                Duration::from_secs_f64(f64::from(sample + 1) * interval)
                    .saturating_sub(started.elapsed()),
            );
        }
    }
    println!("Wrote {samples} aggregate samples to {}", output.display());
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn counter_parser_keeps_only_numeric_kib_values() {
        assert_eq!(
            counters("Rss: 12 kB\nName: private\nPss: invalid kB\nThreads: 3\nSwap: 0 kB\n"),
            BTreeMap::from([("Rss".into(), 12), ("Swap".into(), 0)])
        );
    }
    #[test]
    fn refuses_invalid_sampling_and_existing_output() {
        let temp = tempfile::tempdir().expect("fixture");
        let file = temp.path().join("sample.csv");
        assert!(run(0, &file, 1.0, 1).is_err());
        assert!(run(std::process::id(), &file, f64::NAN, 1).is_err());
        fs::write(&file, b"keep").expect("output");
        assert!(run(std::process::id(), &file, 1.0, 1).is_err());
        assert_eq!(fs::read(file).expect("retained"), b"keep");
    }
}
