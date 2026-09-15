//! Placeholder binary, so `Dockerfile` and `compose.yaml` have something real
//! to build and run. Replace it with your own binary crate and update the
//! `BIN` build arg, or delete it if this crate stays a library.

fn main() {
    println!("{}", example::greet("world"));
}
