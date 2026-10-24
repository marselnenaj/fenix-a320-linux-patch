// SPDX-License-Identifier: MIT
use clap::{Parser, Subcommand};
use std::{
    ffi::OsString,
    path::PathBuf,
    sync::{
        Arc,
        atomic::{AtomicBool, AtomicUsize, Ordering},
    },
};
#[derive(Parser)]
#[command(name="fenix-runtime", version=fenix_patch::VERSION, about="Native Fenix launch and display helpers")]
struct Args {
    #[command(subcommand)]
    command: Action,
}
#[derive(Subcommand)]
enum Action {
    /// Record aggregate counters only, without reading process memory or accounts
    SampleSystemMemory {
        #[arg(long)]
        pid: u32,
        #[arg(long)]
        output: PathBuf,
        #[arg(long, default_value_t = 15.0)]
        interval: f64,
        #[arg(long, default_value_t = 120)]
        samples: u32,
    },
    DisplayRefresh {
        #[arg(long)]
        runtime: PathBuf,
    },
    GameLaunch {
        #[arg(long)]
        runtime: PathBuf,
    },
    WineLaunch {
        #[arg(long)]
        runtime: PathBuf,
        #[arg(required = true, trailing_var_arg = true)]
        args: Vec<OsString>,
    },
}
fn main() {
    let args = Args::parse();
    let stopped = Arc::new(AtomicBool::new(false));
    let last_signal = Arc::new(AtomicUsize::new(0));
    for signal in [signal_hook::consts::SIGINT, signal_hook::consts::SIGTERM] {
        if signal_hook::flag::register(signal, Arc::clone(&stopped)).is_err() {
            std::process::exit(1);
        }
        if signal_hook::flag::register_usize(signal, Arc::clone(&last_signal), signal as usize)
            .is_err()
        {
            std::process::exit(1);
        }
    }
    let result = match args.command {
        Action::SampleSystemMemory {
            pid,
            output,
            interval,
            samples,
        } => fenix_patch::runtime::memory::sample(pid, &output, interval, samples, || {
            stopped.load(Ordering::Relaxed)
        })
        .map(|()| 0),
        Action::DisplayRefresh { runtime } => {
            fenix_patch::runtime::display::run(&runtime, &stopped).map(|()| 0)
        }
        Action::GameLaunch { runtime } => fenix_patch::runtime::launch::game(&runtime),
        Action::WineLaunch { runtime, args } => {
            fenix_patch::runtime::launch::wine(&runtime, &args, &stopped, &last_signal)
        }
    };
    match result {
        Ok(code) => std::process::exit(code),
        Err(error) => {
            eprintln!("Fenix runtime: {error}");
            std::process::exit(if stopped.load(Ordering::Relaxed) {
                128 + last_signal.load(Ordering::Relaxed) as i32
            } else {
                1
            });
        }
    }
}
