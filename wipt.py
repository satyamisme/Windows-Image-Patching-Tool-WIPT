import argparse
import os
import tarfile
import lz4.frame
import shutil
import tempfile
import subprocess
import hashlib

# --- File Type Detection ---
def get_file_type(filepath):
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
def prepare_boot_image_for_patching(image_path):
    file_type = get_file_type(image_path)
    original_input_name = os.path.basename(image_path)
    temp_dir = tempfile.mkdtemp(suffix="_wipt_patch")
    plain_boot_img_path = None

    if file_type == "boot.img":
        shutil.copy(image_path, os.path.join(temp_dir, original_input_name))
        plain_boot_img_path = os.path.join(temp_dir, original_input_name)
        print(f"Image is already boot.img: {plain_boot_img_path}")
    elif file_type == "boot.img.lz4":
        decompressed_name = original_input_name[:-4]
        decompressed_path = os.path.join(temp_dir, decompressed_name)
        print(f"Decompressing {original_input_name} to {decompressed_path}...")
        try:
            with lz4.frame.open(image_path, 'rb') as lz4_file, open(decompressed_path, 'wb') as boot_img_file:
                shutil.copyfileobj(lz4_file, boot_img_file)
            plain_boot_img_path = decompressed_path
            print("Decompression successful.")
        except Exception as e: shutil.rmtree(temp_dir); raise Exception(f"Failed to decompress {image_path}: {e}")
    elif file_type == "boot.tar":
        print(f"Extracting boot.img from {original_input_name}...")
        try:
            with tarfile.open(image_path, 'r') as tar:
                boot_img_member_name = next((m.name for m in tar.getmembers() if m.name in ["boot.img", "recovery.img", "init_boot.img"]),
                                            next((m.name for m in tar.getmembers() if m.name.endswith(".img")), None))
                if boot_img_member_name:
                    tar.extract(boot_img_member_name, path=temp_dir)
                    plain_boot_img_path = os.path.join(temp_dir, boot_img_member_name)
                    print(f"Extracted {boot_img_member_name} to {plain_boot_img_path}")
                else: raise Exception("boot.img not found in tar archive.")
        except Exception as e: shutil.rmtree(temp_dir); raise Exception(f"Failed to extract from {image_path}: {e}")
    elif file_type == "boot.tar.lz4":
        decompressed_tar_name = original_input_name[:-4]
        decompressed_tar_path = os.path.join(temp_dir, decompressed_tar_name)
        print(f"Decompressing {original_input_name} to {decompressed_tar_path}...")
        try:
            with lz4.frame.open(image_path, 'rb') as lz4_file, open(decompressed_tar_path, 'wb') as tar_file:
                shutil.copyfileobj(lz4_file, tar_file)
            print("Decompression to .tar successful.")
            print(f"Extracting boot.img from {decompressed_tar_path}...")
            with tarfile.open(decompressed_tar_path, 'r') as tar:
                boot_img_member_name = next((m.name for m in tar.getmembers() if m.name in ["boot.img", "recovery.img", "init_boot.img"]),
                                            next((m.name for m in tar.getmembers() if m.name.endswith(".img")), None))
                if boot_img_member_name:
                    tar.extract(boot_img_member_name, path=temp_dir)
                    plain_boot_img_path = os.path.join(temp_dir, boot_img_member_name)
                    print(f"Extracted {boot_img_member_name} to {plain_boot_img_path}")
                    if os.path.dirname(boot_img_member_name): # If extracted into a subfolder
                        final_img_loc = os.path.join(temp_dir, os.path.basename(plain_boot_img_path))
                        if plain_boot_img_path != final_img_loc: shutil.move(plain_boot_img_path, final_img_loc); plain_boot_img_path = final_img_loc
                        print(f"Moved extracted image to {plain_boot_img_path}")
                else: raise Exception("boot.img not found in decompressed tar.")
        except Exception as e: shutil.rmtree(temp_dir); raise Exception(f"Failed to process {image_path}: {e}")
    else: shutil.rmtree(temp_dir); raise ValueError(f"Unsupported file type for patching: {file_type} ({image_path})")
    if not plain_boot_img_path or not os.path.exists(plain_boot_img_path):
        if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
        raise Exception(f"Failed to prepare plain boot image from {image_path}")
    return plain_boot_img_path, file_type, temp_dir

# --- Boot Image Repackaging ---
def repackage_patched_boot_image(patched_boot_img_path, original_input_path, original_type, output_dir):
    if not os.path.exists(patched_boot_img_path): raise FileNotFoundError(f"Patched boot img not found: {patched_boot_img_path}")
    original_basename = os.path.basename(original_input_path)
    name_parts = os.path.splitext(original_basename)
    base_name_without_double_ext = os.path.splitext(name_parts[0])[0] if name_parts[0].endswith((".tar", ".img")) else name_parts[0]
    patched_filename_base = base_name_without_double_ext + "_patched"
    os.makedirs(output_dir, exist_ok=True)
    final_output_path = None

    if original_type == "boot.img":
        final_output_path = os.path.join(output_dir, patched_filename_base + ".img")
        shutil.copy(patched_boot_img_path, final_output_path)
    elif original_type == "boot.img.lz4":
        final_output_path = os.path.join(output_dir, patched_filename_base + ".img.lz4")
        try:
            with open(patched_boot_img_path, 'rb') as f_in, lz4.frame.open(final_output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        except Exception as e: raise Exception(f"Failed to compress to {final_output_path}: {e}")
    elif original_type == "boot.tar":
        final_output_path = os.path.join(output_dir, patched_filename_base + ".tar")
        arcname_in_tar = os.path.basename(patched_boot_img_path)
        try:
            with tarfile.open(final_output_path, 'w') as tar: tar.add(patched_boot_img_path, arcname=arcname_in_tar)
        except Exception as e: raise Exception(f"Failed to create tar {final_output_path}: {e}")
    elif original_type == "boot.tar.lz4":
        temp_tar_path = os.path.join(os.path.dirname(patched_boot_img_path), patched_filename_base + ".tar")
        arcname_in_tar = os.path.basename(patched_boot_img_path)
        try:
            with tarfile.open(temp_tar_path, 'w') as tar: tar.add(patched_boot_img_path, arcname=arcname_in_tar)
            final_output_path = os.path.join(output_dir, patched_filename_base + ".tar.lz4")
            with open(temp_tar_path, 'rb') as tar_file, lz4.frame.open(final_output_path, 'wb') as lz4_file:
                shutil.copyfileobj(tar_file, lz4_file)
            os.remove(temp_tar_path)
        except Exception as e:
            if os.path.exists(temp_tar_path): os.remove(temp_tar_path)
            raise Exception(f"Failed to process for {original_type} to {final_output_path}: {e}")
    else: raise ValueError(f"Unsupported original type for repackaging: {original_type}")
    if not final_output_path or not os.path.exists(final_output_path): raise Exception("Repackaging failed.")
    return final_output_path

# --- MagiskPatcher Class ---
class MagiskPatcher:
    def __init__(self, magiskboot_exe_path, assets_dir, working_dir, options=None, logger=print):
        self.magiskboot_exe = magiskboot_exe_path
        self.assets_dir = assets_dir
        self.working_dir = working_dir
        self.options = options if options else {}
        self.logger = logger
        os.makedirs(self.working_dir, exist_ok=True)

    def _exec_magiskboot(self, args, check_return_code=True):
        cmd = [self.magiskboot_exe] + args
        self.logger(f"MagiskPatcher: Executing: {' '.join(cmd)}")
        try:
            process = subprocess.Popen(cmd, cwd=self.working_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            stdout, stderr = process.communicate()
            if stdout: self.logger(f"MagiskPatcher (stdout): {stdout.strip()}")
            if stderr: self.logger(f"MagiskPatcher (stderr): {stderr.strip()}")
            if check_return_code and process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, cmd, output=stdout, stderr=stderr)
            return stdout, stderr, process.returncode
        except FileNotFoundError: self.logger(f"MagiskPatcher: ERROR - magiskboot not found: {self.magiskboot_exe}"); raise
        except subprocess.CalledProcessError as e: self.logger(f"MagiskPatcher: ERROR - magiskboot failed (code {e.returncode})"); raise

    def patch_boot_image(self, plain_boot_image_path, original_boot_img_path_for_repack_ref):
        self.logger(f"MagiskPatcher: Patching {plain_boot_image_path}")
        if not os.access(self.magiskboot_exe, os.X_OK) and os.name != 'nt': self.logger(f"MagiskPatcher: Warning - {self.magiskboot_exe} not executable.")

        internal_boot_img_path = os.path.join(self.working_dir, "boot.img")
        shutil.copy(plain_boot_image_path, internal_boot_img_path)
        self.logger(f"MagiskPatcher: Copied plain boot image to {internal_boot_img_path}")

        patch_args = ['patch', internal_boot_img_path] # Base command
        if self.options.get("KEEPVERITY", False): patch_args.append('keepverity')
        if self.options.get("KEEPFORCEENCRYPT", False): patch_args.append('keepforceencrypt')
        if self.options.get("PATCHVBMETAFLAG", False): patch_args.append('patchvbmetaflag')
        if self.options.get("RECOVERYMODE", False): patch_args.append('recovery')
        if self.options.get("LEGACYSAR", False): patch_args.append('legacysar')

        self.logger(f"MagiskPatcher: magiskboot args: {patch_args}")
        try:
            self._exec_magiskboot(patch_args)
        except Exception as e: raise Exception(f"Magisk boot image patching failed: {e}")

        # Determine output name. Magisk varies this. "new-boot.img" or "magisk_patched..."
        # Using a TARGET_ARCH_SUFFIX like "64" or "32" can affect the output name.
        arch_suffix = self.options.get("TARGET_ARCH_SUFFIX", "")
        possible_names = [f"magisk_patched-{arch_suffix}.img" if arch_suffix else "magisk_patched.img", "new-boot.img"]

        patched_image_path = None
        found_files = os.listdir(self.working_dir)
        self.logger(f"MagiskPatcher: Files in working dir post-patch: {found_files}")
        for name in possible_names:
            if name in found_files: patched_image_path = os.path.join(self.working_dir, name); break
        if not patched_image_path: # Fallback for other magisk_patched variants
             patched_image_path = next((os.path.join(self.working_dir, f) for f in found_files if f.startswith("magisk_patched") and f.endswith(".img")), None)

        if not patched_image_path or not os.path.exists(patched_image_path):
            raise Exception(f"Patched image not found. Expected one of {possible_names} or magisk_patched*.img in {self.working_dir}")
        self.logger(f"MagiskPatcher: Patched image: {patched_image_path}")
        return patched_image_path

# --- Main CLI Handling ---
def handle_extract(args):
    print(f"Extract command: Input: {args.input}, Output: {args.output}")
    # Actual extraction logic here

def handle_patch(args):
    input_image_path = args.input
    output_directory = args.output
    plain_boot_img_prepared_path, original_type, processing_temp_dir = None, None, None
    print(f"Patch command: Input: {input_image_path}, Output Dir: {output_directory}")

    try:
        plain_boot_img_prepared_path, original_type, processing_temp_dir = prepare_boot_image_for_patching(input_image_path)
        print(f"Prepared plain boot image: {plain_boot_img_prepared_path} (Type: {original_type})")
        print(f"Temp dir contents: {os.listdir(processing_temp_dir)}")

        actually_patched_boot_img_path = None
        if args.magisk:
            print("Magisk patch selected.")
            magisk_assets_root = os.path.join(os.getcwd(), "vendor", "magisk-assets")
            magiskboot_exe = os.path.join(magisk_assets_root, "magiskboot.exe" if os.name == 'nt' else "magiskboot")
            os.makedirs(magisk_assets_root, exist_ok=True)

            patcher_options = {
                "KEEPVERITY": args.keep_verity,
                "KEEPFORCEENCRYPT": args.keep_forceencrypt,
                "PATCHVBMETAFLAG": args.patch_vbmeta_flag,
                "RECOVERYMODE": args.recovery_mode,
                "LEGACYSAR": args.legacy_sar
            }
            if args.target_arch in ["arm64", "x64"]: patcher_options["TARGET_ARCH_SUFFIX"] = "64"
            elif args.target_arch in ["arm", "x86"]: patcher_options["TARGET_ARCH_SUFFIX"] = "32"
            else: patcher_options["TARGET_ARCH_SUFFIX"] = "64" # Default

            print(f"MagiskPatcher options: {patcher_options}")
            magisk_patcher = MagiskPatcher(magiskboot_exe, magisk_assets_root, processing_temp_dir, patcher_options, print)
            actually_patched_boot_img_path = magisk_patcher.patch_boot_image(plain_boot_img_prepared_path, input_image_path)
            print(f"MagiskPatcher returned: {actually_patched_boot_img_path}")

        elif args.apatch: # Placeholder for APatch
            print("APatch selected (placeholder).")
            actually_patched_boot_img_path = plain_boot_img_prepared_path
        else: # No patcher selected, just repackage (if that's desired)
            print("No specific patcher selected. Repackaging prepared image.")
            actually_patched_boot_img_path = plain_boot_img_prepared_path

        if actually_patched_boot_img_path and os.path.exists(actually_patched_boot_img_path):
            final_output = repackage_patched_boot_image(actually_patched_boot_img_path, input_image_path, original_type, output_directory)
            print(f"Repackaging complete. Final output: {final_output}")
        else: raise Exception("Patched image not found or not produced.")
    except Exception as e: print(f"Error in patch process: {e}")
    finally:
        if processing_temp_dir and os.path.exists(processing_temp_dir):
            print(f"Cleaning up temp dir: {processing_temp_dir}")
            shutil.rmtree(processing_temp_dir)
        else: print("No temp dir to clean or already cleaned.")

def main():
    parser = argparse.ArgumentParser(description="Windows Image Patching Tool (WIPT)")
    subparsers = parser.add_subparsers(title="Commands", dest="command", required=True)

    parser_extract = subparsers.add_parser("extract", help="Extract firmware images.")
    parser_extract.add_argument("--input", required=True, help="Input file or directory.")
    parser_extract.add_argument("--output", required=True, help="Output directory.")
    parser_extract.set_defaults(func=handle_extract)

    parser_patch = subparsers.add_parser("patch", help="Patch firmware images.")
    parser_patch.add_argument("--input", required=True, help="Input file (boot.img, boot.img.lz4, etc.).")
    parser_patch.add_argument("--output", required=True, help="Output directory for patched file.")

    # General patcher selection
    patcher_group = parser_patch.add_mutually_exclusive_group(required=False) # Make it optional for now
    patcher_group.add_argument("--magisk", action="store_true", help="Perform Magisk patch.")
    patcher_group.add_argument("--apatch", action="store_true", help="Perform APatch (placeholder).")

    # Magisk specific options
    magisk_options_group = parser_patch.add_argument_group("Magisk Options (if --magisk is used)")
    magisk_options_group.add_argument("--keep_verity", action="store_true", help="KEEPVERITY: Preserve AVB/dm-verity.")
    magisk_options_group.add_argument("--keep_forceencrypt", action="store_true", help="KEEPFORCEENCRYPT: Preserve force encryption.")
    magisk_options_group.add_argument("--patch_vbmeta_flag", action="store_true", help="PATCHVBMETAFLAG: Patch VBMeta flags in boot image header.")
    magisk_options_group.add_argument("--recovery_mode", action="store_true", help="RECOVERYMODE: Patch for recovery mode.")
    magisk_options_group.add_argument("--legacy_sar", action="store_true", help="LEGACYSAR: Patch for legacy SAR devices.")
    magisk_options_group.add_argument("--target_arch", type=str, default="arm64", choices=["arm", "arm64", "x86", "x64"],
                                      help="Target architecture for Magisk. Default: arm64.")

    parser_patch.set_defaults(func=handle_patch)

    args = parser.parse_args()
    if hasattr(args, 'func'): args.func(args)
    else: parser.print_help()

if __name__ == "__main__":
    main()
