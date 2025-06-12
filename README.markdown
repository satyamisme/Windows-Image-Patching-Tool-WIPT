# Windows Image Patching Tool (WIPT)

A native Windows CLI tool to extract, compress, and patch firmware images, including tar, lz4, img, sparse, raw, erofs, ext4, dat, br, gz, zip, payload.bin, and super.img, using APatch and Magisk.

## Overview
WIPT enables Windows users to process Android firmware images without WSL or Linux dependencies. It supports a wide range of image formats, integrates APatch for custom patches, and Magisk for rooting. The tool is designed for automation with GitHub Actions and provides a user-friendly CLI.

## Features
- Extract and compress tar, lz4, gz, zip, and br files.
- Handle sparse, raw, ext4, erofs, dat, payload.bin, and super.img formats.
- Patch images with APatch and Magisk for rooting and customization.
- Native Windows execution (no WSL required).
- CLI with format-specific options.
- GitHub Actions for CI/CD, including testing and executable builds.

## Supported Formats
- **tar**: Tape archives for firmware packaging.
- **lz4**: LZ4-compressed images.
- **img**: Generic disk images (e.g., boot.img, system.img).
- **Sparse**: Android sparse images (e.g., system.sparse.img).
- **Raw**: Uncompressed images (ext4, fat32).
- **erofs**: Enhanced Read-Only File System.
- **ext4**: Android partition filesystem.
- **dat**: Android backup data format.
- **br**: Brotli-compressed images.
- **gz**: Gzip-compressed files.
- **zip**: OTA update archives.
- **payload.bin**: Android OTA update containers.
- **super.img**: Multi-partition images (system, vendor, product).

## Installation
### Prerequisites
- Windows 10/11 (64-bit).
- Python 3.10+ ([python.org](https://www.python.org/downloads/), PSF License).
- Git for Windows ([git-scm.com](https://git-scm.com/), GPL v2).
- 7-Zip ([7-zip.org](https://www.7-zip.org/), LGPL + unRAR restrictions).
- APatch ([github.com/bmax121/APatch](https://github.com/bmax121/APatch), GPL v3).
- Magisk ([github.com/topjohnwu/Magisk](https://github.com/topjohnwu/Magisk), GPL v3).

### Steps
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/wipt.git
   cd wipt
   ```
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install 7-Zip:
   - Download from [7-zip.org](https://www.7-zip.org/) or install via Chocolatey:
     ```bash
     choco install 7zip
     ```
4. Run setup script to fetch APatch and Magisk:
   ```bash
   python setup.py
   ```
5. Run the tool:
   ```bash
   python wipt.py --help
   ```

## Usage
```bash
# Extract a sparse image
python wipt.py extract --input system.sparse.img --output extracted/

# Patch a boot image with Magisk
python wipt.py patch --input boot.img --magisk --output patched_boot.img

# Extract payload.bin
python wipt.py extract --input payload.bin --output payload_extracted/

# Patch super.img with APatch
python wipt.py patch --input super.img --apatch --output patched_super.img
```

## Tools and Licenses
| Tool/Library | Source | License |
|--------------|--------|---------|
| Python       | [python.org](https://www.python.org/) | PSF License |
| py7zr        | [github.com/miurahr/py7zr](https://github.com/miurahr/py7zr) | LGPL v2.1 |
| lz4          | [github.com/python-lz4/python-lz4](https://github.com/python-lz4/python-lz4) | BSD 3-Clause |
| brotli       | [github.com/google/brotli](https://github.com/google/brotli) | MIT |
| pylibsparse  | [github.com/akazh/pylibsparse](https://github.com/akazh/pylibsparse) | Apache 2.0 |
| ext4         | [github.com/camlistore/ext4](https://github.com/camlistore/ext4) | MIT |
| erofs-utils  | Custom Python implementation | MIT |
| 7-Zip        | [7-zip.org](https://www.7-zip.org/) | LGPL + unRAR restrictions |
| APatch       | [github.com/bmax121/APatch](https://github.com/bmax121/APatch) | GPL v3 |
| Magisk       | [github.com/topjohnwu/Magisk](https://github.com/topjohnwu/Magisk) | GPL v3 |
| PyInstaller  | [github.com/pyinstaller/pyinstaller](https://github.com/pyinstaller/pyinstaller) | GPL with Bootloader Exception |
| pytest       | [github.com/pytest-dev/pytest](https://github.com/pytest-dev/pytest) | MIT |
| python-binreader | Custom or [github.com/vm03/payload_dumper](https://github.com/vm03/payload_dumper) | MIT or GPL v3 |

## Development Plan
### Phase 1: Setup and Basic File Handling (Weeks 1-2)
- Set up Python project and CLI.
- Support tar, lz4, gz, zip, and sparse images.
- Write basic tests.

### Phase 2: Advanced Image Formats (Weeks 3-5)
- Add ext4, erofs, dat, br, payload.bin, and super.img support.
- Enhance CLI with format-specific options.
- Expand test suite.

### Phase 3: APatch and Magisk Integration (Weeks 6-8)
- Integrate APatch and Magisk for patching.
- Support sparse and super image patching.
- Write integration tests.

### Phase 4: Optimization and Packaging (Weeks 9-10)
- Optimize for large files.
- Create standalone executable.
- Set up GitHub Actions.

### Phase 5: Release (Week 11)
- Publish v1.0.0 release.
- Create issue templates.
- Gather community feedback.

## GitHub Actions
The `.github/workflows/ci.yml` automates linting, testing, building, and releasing:
```yaml
name: CI
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
  workflow aydın: true
jobs:
  lint:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install flake8
      - name: Run lint
        run: flake8 .
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          choco install 7zip
      - name: Run tests
        run: pytest tests/
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          choco install 7zip
      - name: Build executable
        run: pyinstaller --onefile wipt.py
      - name: Upload artifact
        uses: actions/upload-artifact@v3
        with:
          name: wipt-executable
          path: dist/wipt.exe
  release:
    needs: [lint, test, build]
    runs-on: windows-latest
    if: startsWith(github.ref, 'refs/tags/')
    steps:
      - uses: actions/checkout@v3
      - name: Download artifact
        uses: actions/download-artifact@v3
        with:
          name: wipt-executable
          path: dist/
      - name: Create release
        uses: softprops/action-gh-release@v1
        with:
          files: dist/wipt.exe
```

## Contributing
1. Fork the repository.
2. Create a feature branch (`git checkout -b feature/xyz`).
3. Commit changes (`git commit -m "Add xyz feature"`).
4. Push to the branch (`git push origin feature/xyz`).
5. Open a pull request.

## License
MIT License. See [LICENSE](LICENSE) for details.

## Contact
For issues or suggestions, open a GitHub issue or contact [your email].