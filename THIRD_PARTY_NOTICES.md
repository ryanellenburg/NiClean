# Third-party notices

NiClean release artifacts may bundle the following third-party projects to provide “download-and-run” convenience.

## ExifTool

- Project: ExifTool by Phil Harvey
- Website: https://exiftool.org/
- License: Perl Artistic License and/or GPL (see ExifTool distribution)

NiClean uses ExifTool to remove image metadata (e.g. EXIF/XMP/IPTC) using:
`exiftool -all= -overwrite_original`.

## FFmpeg

- Project: FFmpeg
- Website: https://ffmpeg.org/
- License: LGPL or GPL depending on configuration/build options (see FFmpeg distribution)

NiClean uses FFmpeg to remove video container metadata by remuxing where possible.

## Prebuilt FFmpeg binaries

The GitHub Actions workflow downloads FFmpeg binaries from:

- Tyrrrz/FFmpegBin (pre-built FFmpeg binaries for multiple OS/arch)
  https://github.com/Tyrrrz/FFmpegBin

See that repository’s license and the FFmpeg license applicable to the downloaded builds.
