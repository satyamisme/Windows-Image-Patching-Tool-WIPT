import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import os
import threading # For running patching in a separate thread

# Attempt to import the core wipt logic
try:
    from wipt import execute_patching_workflow
except ImportError:
    messagebox.showerror("Import Error", "Could not import 'execute_patching_workflow' from wipt.py. Ensure wipt.py is in the same directory or Python path.")
    execute_patching_workflow = None # Placeholder if import fails


class WiptGuiApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("WIPT - Windows Image Patching Tool GUI")
        self.root.geometry("800x700")

        self.input_image_path = tk.StringVar()
        self.output_dir_path = tk.StringVar()
        self.output_filename = tk.StringVar()
        self.allow_overwrite = tk.BooleanVar(value=True)
        self.patcher_choice = tk.StringVar(value="Magisk")
        self.target_arch = tk.StringVar(value="arm64")
        self.keep_verity = tk.BooleanVar()
        self.keep_forceencrypt = tk.BooleanVar()
        self.patch_vbmeta_flag = tk.BooleanVar()
        self.recovery_mode = tk.BooleanVar()
        self.legacy_sar = tk.BooleanVar()

        self._setup_widgets()
        if execute_patching_workflow is None:
             self.gui_log_callback("CRITICAL: Core patching logic from wipt.py could not be imported. Patching will not work.", "ERROR")


    def _setup_widgets(self):
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(side=tk.TOP, fill=tk.X, expand=False)
        middle_frame = ttk.Frame(self.root, padding="10")
        middle_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, expand=False)

        io_frame = ttk.LabelFrame(top_frame, text="Input/Output", padding="10")
        io_frame.pack(fill=tk.X, expand=True)
        ttk.Label(io_frame, text="Input Image:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(io_frame, textvariable=self.input_image_path, width=60).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(io_frame, text="Browse...", command=self.browse_input_image).grid(row=0, column=2, padx=5, pady=5)
        ttk.Label(io_frame, text="Output Directory:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(io_frame, textvariable=self.output_dir_path, width=60).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(io_frame, text="Browse...", command=self.browse_output_dir).grid(row=1, column=2, padx=5, pady=5)
        ttk.Label(io_frame, text="Output Filename Suggestion:").grid(row=2, column=0, padx=5, pady=5, sticky="w") # Clarified label
        ttk.Entry(io_frame, textvariable=self.output_filename, width=60).grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        # Overwrite option removed as wipt.py's repackage will determine final name, avoiding direct overwrite of input
        # ttk.Checkbutton(io_frame, text="Allow Overwrite", variable=self.allow_overwrite).grid(row=2, column=2, padx=5, pady=5, sticky="w")
        io_frame.columnconfigure(1, weight=1)

        options_outer_frame = ttk.Frame(middle_frame)
        options_outer_frame.pack(side=tk.LEFT, fill=tk.Y, expand=False, padx=(0, 10))
        patcher_frame = ttk.LabelFrame(options_outer_frame, text="Patcher", padding="10")
        patcher_frame.pack(fill=tk.X, expand=True, pady=(0,10))
        ttk.Radiobutton(patcher_frame, text="Magisk", variable=self.patcher_choice, value="Magisk", command=self.on_patcher_choice_change).pack(anchor="w")
        ttk.Radiobutton(patcher_frame, text="APatch (N/A)", variable=self.patcher_choice, value="APatch", state=tk.DISABLED, command=self.on_patcher_choice_change).pack(anchor="w")

        self.magisk_options_frame = ttk.LabelFrame(options_outer_frame, text="Magisk Options", padding="10")
        self.magisk_options_frame.pack(fill=tk.X, expand=True)
        ttk.Label(self.magisk_options_frame, text="Target Arch:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        arch_combobox = ttk.Combobox(self.magisk_options_frame, textvariable=self.target_arch, values=["arm64", "arm", "x86", "x64"], state="readonly")
        arch_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew"); arch_combobox.set("arm64")
        ttk.Checkbutton(self.magisk_options_frame, text="Keep Verity", variable=self.keep_verity).grid(row=1, column=0, columnspan=2, padx=5, pady=2, sticky="w")
        ttk.Checkbutton(self.magisk_options_frame, text="Keep Force Encrypt", variable=self.keep_forceencrypt).grid(row=2, column=0, columnspan=2, padx=5, pady=2, sticky="w")
        ttk.Checkbutton(self.magisk_options_frame, text="Patch VBMeta Flag", variable=self.patch_vbmeta_flag).grid(row=3, column=0, columnspan=2, padx=5, pady=2, sticky="w")
        ttk.Checkbutton(self.magisk_options_frame, text="Recovery Mode", variable=self.recovery_mode).grid(row=4, column=0, columnspan=2, padx=5, pady=2, sticky="w")
        ttk.Checkbutton(self.magisk_options_frame, text="Legacy SAR", variable=self.legacy_sar).grid(row=5, column=0, columnspan=2, padx=5, pady=2, sticky="w")
        self.magisk_options_frame.columnconfigure(1, weight=1)

        log_frame = ttk.LabelFrame(middle_frame, text="Logs", padding="10")
        log_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        self.log_text_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=15, width=60, state='disabled')
        self.log_text_area.pack(fill=tk.BOTH, expand=True)

        action_frame = ttk.Frame(bottom_frame); action_frame.pack(side=tk.LEFT, padx=(0,10))
        self.start_button = ttk.Button(action_frame, text="Start Patching", command=self.start_patching_thread, style="Accent.TButton") # Changed command
        self.start_button.pack(pady=5)
        style = ttk.Style();
        try: style.configure("Accent.TButton", font=('Helvetica', 10, 'bold')) # Simpler style
        except tk.TclError: pass # Ignore if style fails

        self.status_label = ttk.Label(bottom_frame, text="Status: Idle", anchor="w", relief=tk.SUNKEN)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)
        self.gui_log_callback("WIPT GUI Initialized. Ready.", "INFO")

    def on_patcher_choice_change(self): # Enable/disable Magisk options based on patcher
        if self.patcher_choice.get() == "Magisk":
            for child in self.magisk_options_frame.winfo_children():
                child.configure(state='normal')
        else:
            for child in self.magisk_options_frame.winfo_children():
                child.configure(state='disabled')


    def browse_input_image(self):
        filepath = filedialog.askopenfilename(title="Select Boot Image File", filetypes=(("Image Files", "*.img *.lz4 *.tar *.tar.lz4"), ("All files", "*.*")))
        if filepath:
            self.input_image_path.set(filepath)
            self.gui_log_callback(f"Input image selected: {filepath}", "INFO")
            base, ext = os.path.splitext(os.path.basename(filepath))
            if base.endswith(".tar"): base_no_tar, _ = os.path.splitext(base); self.output_filename.set(f"{base_no_tar}_patched{_}{ext}")
            else: self.output_filename.set(f"{base}_patched{ext}")
            self.gui_log_callback(f"Suggested output filename: {self.output_filename.get()}", "DEBUG")

    def browse_output_dir(self):
        dirpath = filedialog.askdirectory(title="Select Output Directory")
        if dirpath: self.output_dir_path.set(dirpath); self.gui_log_callback(f"Output directory selected: {dirpath}", "INFO")

    def start_patching_thread(self): # Wrapper to run actual patching in a thread
        if execute_patching_workflow is None:
            messagebox.showerror("Error", "Core patching logic (wipt.py) not loaded.")
            return

        # Disable button, clear status
        self.start_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: Preparing...")
        self.gui_log_callback("--- Starting Patching Process (via GUI Thread) ---", "ACTION")

        # Gather options for the workflow function
        # Note: 'output_filename' from GUI is a suggestion; core logic determines actual name.
        # The core logic needs 'output_dir'.
        options = {
            "input_path": self.input_image_path.get(),
            "output_dir": self.output_dir_path.get(),
            # "output_filename_suggestion": self.output_filename.get(), # Optional, if core logic uses it
            "patcher": self.patcher_choice.get(),
            "magisk_options": {
                "TARGET_ARCH": self.target_arch.get(), # Already correct key for wipt.py
                "KEEPVERITY": self.keep_verity.get(),
                "KEEPFORCEENCRYPT": self.keep_forceencrypt.get(),
                "PATCHVBMETAFLAG": self.patch_vbmeta_flag.get(),
                "RECOVERYMODE": self.recovery_mode.get(),
                "LEGACYSAR": self.legacy_sar.get(),
            }
        }

        if not options["input_path"] or not options["output_dir"]:
            messagebox.showerror("Error", "Input Image and Output Directory must be specified.")
            self.gui_log_callback("Error: Missing required paths for patching.", "ERROR")
            self.status_label.config(text="Status: Error - Missing paths")
            self.start_button.config(state=tk.NORMAL)
            return

        # Run the core logic in a separate thread to keep GUI responsive
        thread = threading.Thread(target=self._execute_patching_in_thread, args=(options,))
        thread.daemon = True # Allows main app to exit even if thread is running
        thread.start()

    def _execute_patching_in_thread(self, options):
        try:
            self.root.after(0, lambda: self.status_label.config(text="Status: Patching..."))
            # Pass self.gui_log_callback to be used by the workflow
            result_path = execute_patching_workflow(options, self.gui_log_callback)
            # Schedule GUI update on the main thread
            self.root.after(0, lambda: self.on_patching_complete(result_path))
        except Exception as e:
            # Schedule GUI update on the main thread
            self.root.after(0, lambda: self.on_patching_error(str(e)))


    def on_patching_complete(self, output_file_path):
        self.gui_log_callback(f"Patching process completed successfully. Output: {output_file_path}", "SUCCESS")
        self.status_label.config(text=f"Status: Success! Output: {output_file_path}")
        messagebox.showinfo("Success", f"Patching completed!\nOutput saved to: {output_file_path}")
        self.start_button.config(state=tk.NORMAL)

    def on_patching_error(self, error_message):
        self.gui_log_callback(f"Patching process failed: {error_message}", "ERROR")
        self.status_label.config(text=f"Status: Error - {error_message.splitlines()[0]}")
        messagebox.showerror("Error", f"Patching failed:\n{error_message}")
        self.start_button.config(state=tk.NORMAL)

    def gui_log_callback(self, message, level="INFO"): # Renamed from log_message
        self.log_text_area.configure(state='normal')
        self.log_text_area.insert(tk.END, f"[{level}] {message}\n")
        self.log_text_area.configure(state='disabled')
        self.log_text_area.see(tk.END)


if __name__ == '__main__':
    root = tk.Tk()
    app = WiptGuiApp(root)
    root.mainloop()
