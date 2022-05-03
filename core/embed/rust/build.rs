#[cfg(feature = "test")]
use std::ffi::OsStr;

fn main() {
    #[cfg(feature = "test")]
    link_core_objects();
}


#[cfg(feature = "test")]
fn link_core_objects() {
    let crate_path = env::var("CARGO_MANIFEST_DIR").unwrap();
    let build_path = format!("{}/../../build/unix", crate_path);

    // List of object filenames to ignore in the `embed` and `vendor` directory
    let embed_blocklist = [OsStr::new("main_main.o")];
    let vendor_blocklist = [OsStr::new("gen_context.o")];

    // Collect all objects that the `core` library uses, and link it in. We have to
    // make sure to avoid the object with the `_main` symbol, so we don't get any
    // duplicates.
    let mut cc = cc::Build::new();
    for obj in glob::glob(&format!("{}/embed/**/*.o", build_path)).unwrap() {
        let obj = obj.unwrap();
        if embed_blocklist.contains(&obj.file_name().unwrap()) {
            // Ignore.
        } else {
            cc.object(obj);
        }
    }

    for obj in glob::glob(&format!("{}/vendor/**/*.o", build_path)).unwrap() {
        let obj = obj.unwrap();
        if vendor_blocklist.contains(&obj.file_name().unwrap()) {
            // Ignore.
        } else {
            cc.object(obj);
        }
    }

    // Compile all the objects into a static library and link it in automatically.
    cc.compile("core_lib");

    println!("cargo:rustc-link-lib=SDL2");
    println!("cargo:rustc-link-lib=SDL2_image");
}
