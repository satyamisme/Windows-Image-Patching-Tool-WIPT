import argparse
import os
import tarfile
import lz4.frame
import shutil
import tempfile
import subprocess
import hashlib

# --- File Type Detection ---
def get_file_type(filepath): # No changes
    filename = os.path.basename(filepath)
    if filename.endswith(".tar.lz4"): return "boot.tar.lz4"
    if filename.endswith(".tar"): return "boot.tar"
    if filename.endswith(".img.lz4") or filepath.endswith(".lz4"):
        try:
            with open(filepath, 'rb') as f:
                if f.read(4) == b'\x04\x22\x4D\x18':
                    return "boot.img.lz4" if filename.endswith(".img.lz4") else "lz4_generic"
        except IOError: pass
        return "boot.img.lz4" if filename.endswith(".img.lz4") else "lz4_generic"
    if filename.endswith(".img"): return "boot.img"
    return "unknown"

# --- Boot Image Preparation ---
def prepare_boot_image_for_patching(image_path, log_callback): # No changes
    log_callback(f"Preparing boot image for: {image_path}", "INFO")
    file_type = get_file_type(image_path)
    original_input_name = os.path.basename(image_path)
    temp_dir = tempfile.mkdtemp(suffix="_wipt_patch")
    plain_boot_img_path = None
    original_boot_img_arcname = None
    log_callback(f"Detected file type: {file_type}", "DEBUG")
    if file_type == "boot.img":
        shutil.copy(image_path, os.path.join(temp_dir, original_input_name))
        plain_boot_img_path = os.path.join(temp_dir, original_input_name)
        log_callback(f"Image is already boot.img: {plain_boot_img_path}", "INFO")
    elif file_type == "boot.img.lz4":
        decompressed_name = original_input_name[:-4]
        decompressed_path = os.path.join(temp_dir, decompressed_name)
        log_callback(f"Decompressing {original_input_name} to {decompressed_path}...", "INFO")
        try:
            with lz4.frame.open(image_path, 'rb') as lz4_file, open(decompressed_path, 'wb') as boot_img_file:
                shutil.copyfileobj(lz4_file, boot_img_file)
            plain_boot_img_path = decompressed_path; log_callback("Decompression successful.", "INFO")
        except Exception as e: shutil.rmtree(temp_dir); log_callback(f"Failed to decompress {image_path}: {e}", "ERROR"); raise
    elif file_type == "boot.tar":
        log_callback(f"Extracting boot image from {original_input_name}...", "INFO")
        try:
            with tarfile.open(image_path, 'r') as tar:
                preferred_names = ["boot.img", "recovery.img", "init_boot.img"]
                boot_member_info = next((m for m in tar.getmembers() if m.name in preferred_names and m.isfile()), None)
                if not boot_member_info:
                    boot_member_info = next((m for m in tar.getmembers() if m.name.endswith(".img") and m.isfile()), None)
                    if boot_member_info: log_callback(f"Using generic .img file from tar: {boot_member_info.name}", "WARN")
                if boot_member_info:
                    original_boot_img_arcname = boot_member_info.name
                    tar.extract(boot_member_info, path=temp_dir)
                    plain_boot_img_path = os.path.join(temp_dir, original_boot_img_arcname)
                    log_callback(f"Extracted '{original_boot_img_arcname}' to {plain_boot_img_path}", "INFO")
                else: log_callback("Suitable boot image not found in tar archive.", "ERROR"); raise Exception("Boot image not in tar.")
        except Exception as e: shutil.rmtree(temp_dir); log_callback(f"Failed to extract from {image_path}: {e}", "ERROR"); raise
    elif file_type == "boot.tar.lz4":
        decompressed_tar_name = original_input_name[:-4]
        decompressed_tar_path = os.path.join(temp_dir, decompressed_tar_name)
        log_callback(f"Decompressing {original_input_name} to {decompressed_tar_path}...", "INFO")
        try:
            with lz4.frame.open(image_path, 'rb') as lz4_file, open(decompressed_tar_path, 'wb') as tar_file:
                shutil.copyfileobj(lz4_file, tar_file)
            log_callback("Decompression to .tar successful.", "INFO")
            log_callback(f"Extracting boot image from {decompressed_tar_path}...", "INFO")
            with tarfile.open(decompressed_tar_path, 'r') as tar:
                preferred_names = ["boot.img", "recovery.img", "init_boot.img"]
                boot_member_info = next((m for m in tar.getmembers() if m.name in preferred_names and m.isfile()), None)
                if not boot_member_info:
                    boot_member_info = next((m for m in tar.getmembers() if m.name.endswith(".img") and m.isfile()), None)
                    if boot_member_info: log_callback(f"Using generic .img from tar: {boot_member_info.name}", "WARN")
                if boot_member_info:
                    original_boot_img_arcname = boot_member_info.name
                    tar.extract(boot_member_info, path=temp_dir)
                    plain_boot_img_path = os.path.join(temp_dir, original_boot_img_arcname)
                    log_callback(f"Extracted '{original_boot_img_arcname}' to {plain_boot_img_path}", "INFO")
                else: log_callback("Suitable boot image not found in decompressed tar.", "ERROR"); raise Exception("Boot image not in tar.lz4.")
        except Exception as e: shutil.rmtree(temp_dir); log_callback(f"Failed to process {image_path}: {e}", "ERROR"); raise
    else:
        shutil.rmtree(temp_dir); log_callback(f"Unsupported file type: {file_type} ({image_path})", "ERROR"); raise ValueError(f"Unsupported file type: {file_type}")
    if not plain_boot_img_path or not os.path.exists(plain_boot_img_path):
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        log_callback(f"Failed to prepare plain boot image from {image_path}", "ERROR"); raise Exception("Failed to prepare boot image.")
    return plain_boot_img_path, file_type, temp_dir, original_boot_img_arcname

# --- Boot Image Repackaging ---
def repackage_patched_boot_image(patched_boot_img_path, original_input_path, original_type, output_dir,
                                 log_callback, original_boot_img_arcname=None,
                                 custom_output_filename=None, allow_overwrite=False): # New args
    log_callback(f"Repackaging patched image: {patched_boot_img_path}", "INFO")
    if not os.path.exists(patched_boot_img_path):
        log_callback(f"Patched boot img not found: {patched_boot_img_path}", "ERROR"); raise FileNotFoundError("Patched image missing.")

    os.makedirs(output_dir, exist_ok=True)

    final_name = ""
    if custom_output_filename and custom_output_filename.strip():
        final_name = custom_output_filename.strip()
        log_callback(f"Using custom output filename: {final_name}", "INFO")
    else:
        original_basename = os.path.basename(original_input_path)
        name_parts = []
        temp_basename = original_basename
        # Handle multi-part extensions like .tar.lz4 or .img.gz
        while True:
            temp_basename, ext = os.path.splitext(temp_basename)
            if not ext: # No more extensions
                name_parts.insert(0, temp_basename)
                break
            name_parts.insert(0, ext)
            if not temp_basename: # Handle cases like ".bashrc"
                name_parts.insert(0, "")
                break

        # name_parts is now like ['boot', '.img'] or ['firmware', '.tar', '.lz4']
        base = name_parts[0]
        extensions = "".join(name_parts[1:])
        final_name = f"{base}_patched{extensions}"
        log_callback(f"Using default output filename: {final_name}", "INFO")

    final_output_path = os.path.join(output_dir, final_name)

    if os.path.exists(final_output_path):
        if not allow_overwrite:
            log_callback(f"Output file {final_output_path} already exists and overwrite is not allowed.", "ERROR")
            raise FileExistsError(f"Output file {final_output_path} exists; overwrite not allowed.")
        else:
            log_callback(f"Output file {final_output_path} already exists and will be overwritten.", "WARN")

    if original_type == "boot.img":
        log_callback(f"Copying patched boot.img to {final_output_path}", "INFO")
        shutil.copy2(patched_boot_img_path, final_output_path) # Use copy2 to preserve metadata if possible
    elif original_type == "boot.img.lz4":
        log_callback(f"Compressing patched boot.img to {final_output_path} (LZ4)...", "INFO")
        try:
            with open(patched_boot_img_path, 'rb') as f_in, lz4.frame.open(final_output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            log_callback("LZ4 compression successful.", "INFO")
        except Exception as e: log_callback(f"Failed to LZF compress {final_output_path}: {e}", "ERROR"); raise
    elif original_type == "boot.tar":
        log_callback(f"Rebuilding TAR archive at {final_output_path}, replacing '{original_boot_img_arcname}'...", "INFO")
        try:
            with tarfile.open(original_input_path, 'r') as orig_tar, tarfile.open(final_output_path, 'w') as new_tar:
                for member in orig_tar.getmembers():
                    if original_boot_img_arcname and member.name == original_boot_img_arcname:
                        new_tar.add(patched_boot_img_path, arcname=original_boot_img_arcname)
                        log_callback(f"  Added patched boot image as '{original_boot_img_arcname}'", "DEBUG")
                    else:
                        if member.isfile(): extracted_file = orig_tar.extractfile(member); new_tar.addfile(member, fileobj=extracted_file)
                        else: new_tar.addfile(member)
                log_callback("TAR archive rebuild successful.", "INFO")
        except Exception as e: log_callback(f"Failed to rebuild tar {final_output_path}: {e}", "ERROR"); raise
    elif original_type == "boot.tar.lz4":
        temp_dir_for_tarlz4 = os.path.dirname(patched_boot_img_path)
        # Use original_input_path's basename for temp tar to avoid collisions if multiple .tar.lz4 are processed
        original_input_basename_noext = os.path.splitext(os.path.splitext(os.path.basename(original_input_path))[0])[0]
        temp_original_tar_path = os.path.join(temp_dir_for_tarlz4, original_input_basename_noext + "_orig_temp.tar")
        temp_new_patched_tar_path = os.path.join(temp_dir_for_tarlz4, os.path.splitext(final_name)[0] + "_temp.tar") # Use final_name base for temp patched tar

        log_callback(f"Decompressing original {original_input_path} to {temp_original_tar_path} for rebuild...", "INFO")
        try:
            with lz4.frame.open(original_input_path, 'rb') as lz4_in, open(temp_original_tar_path, 'wb') as tar_out:
                shutil.copyfileobj(lz4_in, tar_out)
            log_callback(f"Rebuilding TAR to {temp_new_patched_tar_path}, replacing '{original_boot_img_arcname}'...", "INFO")
            with tarfile.open(temp_original_tar_path, 'r') as orig_tar, \
                 tarfile.open(temp_new_patched_tar_path, 'w') as new_tar:
                for member in orig_tar.getmembers():
                    if original_boot_img_arcname and member.name == original_boot_img_arcname:
                        new_tar.add(patched_boot_img_path, arcname=original_boot_img_arcname)
                    else:
                        if member.isfile(): new_tar.addfile(member, fileobj=orig_tar.extractfile(member))
                        else: new_tar.addfile(member)
            log_callback(f"Compressing {temp_new_patched_tar_path} to {final_output_path}...", "INFO")
            with open(temp_new_patched_tar_path, 'rb') as tar_in, lz4.frame.open(final_output_path, 'wb') as lz4_out:
                shutil.copyfileobj(tar_in, lz4_out)
            log_callback("TAR.LZ4 repackaging successful.", "INFO")
        except Exception as e: log_callback(f"Failed to process for {original_type} to {final_output_path}: {e}", "ERROR"); raise
        finally:
            for p_path in [temp_original_tar_path, temp_new_patched_tar_path]:
                if os.path.exists(p_path): os.remove(p_path)
    else:
        log_callback(f"Unsupported original type for repackaging: {original_type}", "ERROR")
        raise ValueError(f"Unsupported type for repackaging: {original_type}")
    if not os.path.exists(final_output_path):
        log_callback("Repackaging failed, output file not found.", "ERROR"); raise Exception("Repackaging failed.")
    return final_output_path

# --- MagiskPatcher Class (no changes from previous step) ---
class MagiskPatcher:
    def __init__(self, magiskboot_exe_path, assets_dir, working_dir, options=None, logger=print):
        self.magiskboot_exe = magiskboot_exe_path; self.assets_dir = assets_dir; self.working_dir = working_dir
        self.options = options if options else {}; self.log_callback = logger; os.makedirs(self.working_dir, exist_ok=True)
        self.target_arch = self.options.get("TARGET_ARCH", "arm64")
        self.log_callback(f"MagiskPatcher: Target arch: {self.target_arch}", "DEBUG")
        self.magisk_asset_name = f"magisk_{self.target_arch}"; self.magiskinit_asset_name = f"magiskinit_{self.target_arch}"
        self.initld_asset_name = f"initld_{self.target_arch}"
        essential = {self.magisk_asset_name: os.path.join(self.assets_dir, self.magisk_asset_name),
                     self.magiskinit_asset_name: os.path.join(self.assets_dir, self.magiskinit_asset_name)}
        for name, path in essential.items():
            if not os.path.exists(path): self.log_callback(f"MagiskPatcher: Asset '{name}' not found: {path}", "ERROR"); raise FileNotFoundError(f"Asset '{name}' not found: {path}")
            self.log_callback(f"MagiskPatcher: Found asset: {path}", "DEBUG")
        self.initld_asset_path = os.path.join(self.assets_dir, self.initld_asset_name)
        if not os.path.exists(self.initld_asset_path): self.log_callback(f"MagiskPatcher: Warn - Asset '{self.initld_asset_name}' not found: {self.initld_asset_path}", "WARN"); self.initld_asset_path = None
        else: self.log_callback(f"MagiskPatcher: Found asset: {self.initld_asset_path}", "DEBUG")
        self.stub_apk_path = os.path.join(self.assets_dir, "stub.apk")
        if not os.path.exists(self.stub_apk_path): self.log_callback(f"MagiskPatcher: Warn - stub.apk not found: {self.stub_apk_path}", "WARN"); self.stub_apk_path = None
    def _exec_magiskboot(self, args, check_return_code=True, env_vars=None):
        cmd = [self.magiskboot_exe] + args; self.log_callback(f"MagiskPatcher: Executing: {' '.join(cmd)}", "CMD")
        try:
            env = os.environ.copy(); env.update(env_vars or {})
            p = subprocess.Popen(cmd, cwd=self.working_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            out, err = p.communicate()
            if out: self.log_callback(f"MagiskPatcher (stdout): {out.strip()}", "DEBUG")
            if err: self.log_callback(f"MagiskPatcher (stderr): {err.strip()}", "DEBUG")
            if check_return_code and p.returncode != 0:
                self.log_callback(f"MagiskPatcher: ERROR - magiskboot command failed (code {p.returncode})", "ERROR"); raise subprocess.CalledProcessError(p.returncode, cmd, output=out, stderr=err)
            return out, err, p.returncode
        except FileNotFoundError: self.log_callback(f"MagiskPatcher: ERROR - magiskboot not found: {self.magiskboot_exe}", "ERROR"); raise
        except subprocess.CalledProcessError as e: self.log_callback(f"MagiskPatcher: ERROR - magiskboot failed (code {e.returncode})", "ERROR"); raise
    def _compress_to_xz(self, source_path, dest_path_xz):
        self.log_callback(f"MagiskPatcher: Compressing {source_path} to {dest_path_xz}...", "INFO")
        if not os.path.exists(source_path): self.log_callback(f"Cannot compress, src missing: {source_path}","ERROR"); raise FileNotFoundError(f"Src missing: {source_path}")
        self._exec_magiskboot(['xz', source_path, dest_path_xz])
        if not os.path.exists(dest_path_xz): self.log_callback(f"XZ compression failed, output missing: {dest_path_xz}", "ERROR"); raise Exception("XZ compression failed.")
        self.log_callback(f"MagiskPatcher: Compressed to {dest_path_xz}", "INFO")
    def patch_boot_image(self, plain_boot_image_path, original_boot_img_path_for_repack_ref):
        self.log_callback(f"MagiskPatcher: Patching {plain_boot_image_path} for arch {self.target_arch}", "INFO")
        local_magiskinit_path = os.path.join(self.working_dir, "magiskinit_for_ramdisk")
        shutil.copy(os.path.join(self.assets_dir, self.magiskinit_asset_name), local_magiskinit_path)
        local_magisk_path = os.path.join(self.working_dir, f"magisk_for_ramdisk_{self.target_arch}")
        shutil.copy(os.path.join(self.assets_dir, self.magisk_asset_name), local_magisk_path)
        local_initld_path, initld_xz_path, local_stub_path, stub_xz_path = None, None, None, None
        if self.initld_asset_path: local_initld_path = os.path.join(self.working_dir, "initld_for_ramdisk"); shutil.copy(self.initld_asset_path, local_initld_path)
        if self.stub_apk_path: local_stub_path = os.path.join(self.working_dir, "stub_for_ramdisk.apk"); shutil.copy(self.stub_apk_path, local_stub_path)
        magisk_xz_name_in_ramdisk = f"magisk_{self.target_arch}.xz"; magisk_xz_path = os.path.join(self.working_dir, magisk_xz_name_in_ramdisk)
        self._compress_to_xz(local_magisk_path, magisk_xz_path)
        if local_initld_path: initld_xz_path = os.path.join(self.working_dir, "init-ld.xz"); self._compress_to_xz(local_initld_path, initld_xz_path)
        if local_stub_path: stub_xz_path = os.path.join(self.working_dir, "stub.xz"); self._compress_to_xz(local_stub_path, stub_xz_path)
        internal_boot_img_path = os.path.join(self.working_dir, "boot.img"); shutil.copy(plain_boot_image_path, internal_boot_img_path)
        self._exec_magiskboot(['unpack', internal_boot_img_path])
        ramdisk_cpio_path = os.path.join(self.working_dir, "ramdisk.cpio");
        if not os.path.exists(ramdisk_cpio_path): self.log_callback(f"ramdisk.cpio missing after unpack in {self.working_dir}", "ERROR"); raise FileNotFoundError("ramdisk.cpio missing")
        cpio_cmds = [f'add 0750 init {local_magiskinit_path}', 'mkdir 0750 overlay.d', 'mkdir 0750 overlay.d/sbin',
                       f'add 0644 overlay.d/sbin/{magisk_xz_name_in_ramdisk} {magisk_xz_path}']
        if initld_xz_path: cpio_cmds.append(f'add 0644 overlay.d/sbin/init-ld.xz {initld_xz_path}')
        if stub_xz_path: cpio_cmds.append(f'add 0644 overlay.d/stub.xz {stub_xz_path}')
        env = {opt.upper(): "true" for opt in ["KEEPVERITY", "KEEPFORCEENCRYPT", "PATCHVBMETAFLAG", "RECOVERYMODE", "LEGACYSAR"] if self.options.get(opt)}
        for cmd_str in cpio_cmds: self._exec_magiskboot(['cpio', ramdisk_cpio_path, cmd_str], env_vars=env)
        self._exec_magiskboot(['repack', internal_boot_img_path], env_vars=env)
        files_to_clean = [local_magiskinit_path, local_magisk_path, magisk_xz_path, local_initld_path, initld_xz_path, local_stub_path, stub_xz_path]
        for f_path in files_to_clean:
            if f_path and os.path.exists(f_path): os.remove(f_path)
        patched_img_path = os.path.join(self.working_dir, "new-boot.img")
        if not os.path.exists(patched_img_path): self.log_callback(f"Patched 'new-boot.img' missing in {self.working_dir}", "ERROR"); raise Exception("Patched 'new-boot.img' missing")
        self.log_callback(f"MagiskPatcher: Patched image: {patched_img_path}", "INFO"); return patched_img_path

# --- Core Workflow Function ---
def execute_patching_workflow(options, log_callback):
    log_callback("--- Starting WIPT Patching Workflow ---", "ACTION")
    input_image_path = options.get("input_path")
    output_directory = options.get("output_dir")
    custom_output_filename = options.get("output_filename") # From GUI's suggestion or CLI
    allow_overwrite_opt = options.get("allow_overwrite", False) # Default to False if not provided

    if not input_image_path or not output_directory:
        log_callback("Error: Input path or output directory not provided.", "ERROR"); raise ValueError("Missing input/output paths.")
    plain_boot_img_prepared_path, original_type, processing_temp_dir, original_boot_img_arcname = None, None, None, None
    try:
        plain_boot_img_prepared_path, original_type, processing_temp_dir, original_boot_img_arcname = \
            prepare_boot_image_for_patching(input_image_path, log_callback)
        log_callback(f"Prepared: {plain_boot_img_prepared_path} (Type: {original_type}, Arc: {original_boot_img_arcname})", "INFO")
        if processing_temp_dir: log_callback(f"Temp dir contents: {os.listdir(processing_temp_dir)}", "DEBUG")

        actually_patched_boot_img_path = None
        if options.get("patcher") == "Magisk":
            log_callback("Magisk patch selected in workflow.", "INFO")
            magisk_assets_root = os.path.join(os.getcwd(), "vendor", "magisk-assets")
            magiskboot_exe = os.path.join(magisk_assets_root, "magiskboot.exe" if os.name == 'nt' else "magiskboot")
            os.makedirs(magisk_assets_root, exist_ok=True)
            magisk_patcher_opts = options.get("magisk_options", {})
            if "TARGET_ARCH" not in magisk_patcher_opts : magisk_patcher_opts["TARGET_ARCH"] = options.get("target_arch", "arm64") # Ensure TARGET_ARCH is there
            log_callback(f"MagiskPatcher options for workflow: {magisk_patcher_opts}", "DEBUG")
            magisk_patcher = MagiskPatcher(magiskboot_exe, magisk_assets_root, processing_temp_dir, magisk_patcher_opts, log_callback)
            actually_patched_boot_img_path = magisk_patcher.patch_boot_image(plain_boot_img_prepared_path, input_image_path)
            log_callback(f"MagiskPatcher returned: {actually_patched_boot_img_path}", "INFO")
        elif options.get("patcher") == "APatch":
            log_callback("APatch selected (placeholder).", "WARN"); actually_patched_boot_img_path = plain_boot_img_prepared_path
        else:
            log_callback("No patcher (or not Magisk). Repackaging as is.", "INFO"); actually_patched_boot_img_path = plain_boot_img_prepared_path

        if actually_patched_boot_img_path and os.path.exists(actually_patched_boot_img_path):
            final_output_file_path = repackage_patched_boot_image(
                actually_patched_boot_img_path, input_image_path, original_type, output_directory,
                log_callback, original_boot_img_arcname=original_boot_img_arcname,
                custom_output_filename=custom_output_filename, # Pass new options
                allow_overwrite=allow_overwrite_opt         # Pass new options
            )
            log_callback(f"Workflow complete. Output: {final_output_file_path}", "SUCCESS"); return final_output_file_path
        else:
            log_callback("Error: Patched image missing post-patching.", "ERROR"); raise Exception("Patched image missing.")
    except Exception as e: log_callback(f"Error in workflow: {e}", "ERROR"); raise
    finally:
        if processing_temp_dir and os.path.exists(processing_temp_dir):
            log_callback(f"Cleaning temp dir: {processing_temp_dir}", "INFO"); shutil.rmtree(processing_temp_dir)
        else: log_callback("No temp dir to clean or already cleaned.", "DEBUG")

# --- Main CLI Handling ---
def handle_patch_cli(args):
    options = { "input_path": args.input, "output_dir": args.output,
                "patcher": "Magisk" if args.magisk else ("APatch" if args.apatch else None),
                "output_filename": args.output_filename if hasattr(args, 'output_filename') else None, # Get from args if exists
                "allow_overwrite": args.allow_overwrite if hasattr(args, 'allow_overwrite') else False, # Get from args
                "magisk_options": { "TARGET_ARCH": args.target_arch, "KEEPVERITY": args.keep_verity,
                                    "KEEPFORCEENCRYPT": args.keep_forceencrypt, "PATCHVBMETAFLAG": args.patch_vbmeta_flag,
                                    "RECOVERYMODE": args.recovery_mode, "LEGACYSAR": args.legacy_sar, } }
    def cli_log_callback(message, level="INFO"): print(f"[{level}] {message}")
    try:
        final_path = execute_patching_workflow(options, cli_log_callback)
        cli_log_callback(f"CLI: Success. Output: {final_path}", "SUCCESS")
    except Exception as e: cli_log_callback(f"CLI: Failed. Error: {e}", "ERROR")

def handle_extract_cli(args):
    def cli_log_callback(message, level="INFO"): print(f"[{level}] {message}")
    cli_log_callback(f"Extract (CLI): Input: {args.input}, Output: {args.output}", "INFO")

def main_cli():
    parser = argparse.ArgumentParser(description="WIPT - CLI")
    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True)
    p_extract = subparsers.add_parser("extract", help="Extract firmware.")
    p_extract.add_argument("--input", required=True); p_extract.add_argument("--output", required=True)
    p_extract.set_defaults(func=handle_extract_cli)
    p_patch = subparsers.add_parser("patch", help="Patch firmware.")
    p_patch.add_argument("--input", required=True); p_patch.add_argument("--output", required=True)
    p_patch.add_argument("--output-filename", help="Optional custom output filename.") # New CLI arg
    p_patch.add_argument("--allow-overwrite", action="store_true", help="Allow overwriting output file if it exists.") # New CLI arg
    patcher_group = p_patch.add_mutually_exclusive_group(required=False)
    patcher_group.add_argument("--magisk", action="store_true"); patcher_group.add_argument("--apatch", action="store_true")
    magisk_opts = p_patch.add_argument_group("Magisk Options")
    magisk_opts.add_argument("--target_arch",type=str,default="arm64",choices=["arm","arm64","x86","x64"])
    magisk_opts.add_argument("--keep_verity",action="store_true"); magisk_opts.add_argument("--keep_forceencrypt",action="store_true")
    magisk_opts.add_argument("--patch_vbmeta_flag",action="store_true"); magisk_opts.add_argument("--recovery_mode",action="store_true")
    magisk_opts.add_argument("--legacy_sar",action="store_true")
    p_patch.set_defaults(func=handle_patch_cli)
    args = parser.parse_args()
    if args.command == "patch" and not args.magisk and not args.apatch:
        if any([args.keep_verity, args.keep_forceencrypt, args.patch_vbmeta_flag, args.recovery_mode, args.legacy_sar,
                (args.target_arch != "arm64"), args.output_filename, args.allow_overwrite]):
            args.magisk = True # Imply Magisk if any of its specific options or new general patch options are used
    if hasattr(args, 'func'): args.func(args)
    else: parser.print_help()

if __name__ == "__main__":
    main_cli()
