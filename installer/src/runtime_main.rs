// SPDX-License-Identifier: MIT
use clap::{Parser, Subcommand};
use std::{
    ffi::OsString,
    path::PathBuf,
    sync::{Arc, atomic::AtomicBool},
};
#[derive(Parser)]
#[command(name="fenix-runtime", version=fenix_patch::VERSION, about="Native Fenix launch and display helpers")]
struct Args {
    #[command(subcommand)]
    command: Action,
}
#[derive(Subcommand)]
enum Action {
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
    for signal in [signal_hook::consts::SIGINT, signal_hook::consts::SIGTERM] {
        if signal_hook::flag::register(signal, Arc::clone(&stopped)).is_err() {
            std::process::exit(1);
        }
    }
    let result = match args.command {
        Action::DisplayRefresh { runtime } => {
            fenix_patch::runtime::display::run(&runtime, &stopped).map(|()| 0)
        }
        Action::GameLaunch { runtime } => fenix_patch::runtime::launch::game(&runtime),
        Action::WineLaunch { runtime, args } => {
            fenix_patch::runtime::launch::wine(&runtime, &args, &stopped)
        }
    };
    match result {
        Ok(code) => std::process::exit(code),
        Err(error) => {
            eprintln!("Fenix runtime: {error}");
            std::process::exit(1);
        }
    }
}
