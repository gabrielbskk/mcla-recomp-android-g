import pathlib
import struct
import tempfile
import unittest
import zipfile

from scripts import package_android_xapk, verify_android_apk


ROOT = pathlib.Path(__file__).resolve().parents[1]


class VerifyAndroidApkTest(unittest.TestCase):
    @staticmethod
    def make_dex(descriptor, class_defined=True):
        string_data_offset = 0x98
        data = bytearray(string_data_offset + len(descriptor) + 2)
        data[:8] = b"dex\n035\x00"
        struct.pack_into("<I", data, 0x20, len(data))
        struct.pack_into("<I", data, 0x24, 0x70)
        struct.pack_into("<I", data, 0x28, 0x12345678)
        struct.pack_into("<II", data, 0x38, 1, 0x70)  # string_ids
        struct.pack_into("<II", data, 0x40, 1, 0x74)  # type_ids
        struct.pack_into("<II", data, 0x60, 1 if class_defined else 0, 0x78)
        struct.pack_into("<I", data, 0x70, string_data_offset)
        struct.pack_into("<I", data, 0x74, 0)  # descriptor string index
        if class_defined:
            struct.pack_into("<I", data, 0x78, 0)  # class_idx
        data[string_data_offset] = len(descriptor)
        data[string_data_offset + 1:string_data_offset + 1 + len(descriptor)] = descriptor
        return bytes(data)

    def make_apk(self, directory, *, dex=True, importer=True, importer_defined=True, libraries=True):
        apk = pathlib.Path(directory) / "candidate.apk"
        with zipfile.ZipFile(apk, "w") as archive:
            if dex:
                descriptor = (b"Lorg/apache/commons/compress/archivers/zip/ZipArchiveInputStream;"
                              if importer else b"Lorg/mcla/recomp/DataImportService;")
                archive.writestr(
                    "classes.dex",
                    self.make_dex(descriptor, class_defined=importer_defined),
                )
            if libraries:
                for library in verify_android_apk.REQUIRED_NATIVE_LIBRARIES:
                    archive.writestr(f"lib/arm64-v8a/{library}", b"ELF")
        return apk

    @staticmethod
    def badging(package="org.mcla.recomp.openbeta"):
        return "\n".join((
            f"package: name='{package}' versionCode='3' versionName='0.1.2-experimental'",
            "application-label:'MCLA Recomp (Experimental)'",
        ))

    def test_parse_badging_reads_package_and_label(self):
        parsed = verify_android_apk.parse_badging(self.badging())
        self.assertEqual(parsed.package_name, "org.mcla.recomp.openbeta")
        self.assertEqual(parsed.application_label, "MCLA Recomp (Experimental)")

    def test_verify_accepts_open_beta_with_importer_and_all_native_libraries(self):
        with tempfile.TemporaryDirectory() as directory:
            errors = verify_android_apk.verify_archive(
                self.make_apk(directory), self.badging(), "org.mcla.recomp.openbeta"
            )
        self.assertEqual(errors, [])

    def test_verify_rejects_stale_package(self):
        with tempfile.TemporaryDirectory() as directory:
            errors = verify_android_apk.verify_archive(
                self.make_apk(directory), self.badging("org.mcla.recomp"),
                "org.mcla.recomp.openbeta",
            )
        self.assertTrue(any("package" in error for error in errors))

    def test_verify_rejects_missing_zip_import_dependency(self):
        with tempfile.TemporaryDirectory() as directory:
            errors = verify_android_apk.verify_archive(
                self.make_apk(directory, importer=True, importer_defined=False), self.badging(),
                "org.mcla.recomp.openbeta",
            )
        self.assertTrue(any("ZipArchiveInputStream" in error for error in errors))

    def test_verify_rejects_missing_native_library(self):
        with tempfile.TemporaryDirectory() as directory:
            errors = verify_android_apk.verify_archive(
                self.make_apk(directory, libraries=False), self.badging(),
                "org.mcla.recomp.openbeta",
            )
        self.assertTrue(any("libmain.so" in error for error in errors))

    def test_xapk_metadata_uses_the_open_beta_package(self):
        self.assertEqual(package_android_xapk.PACKAGE_NAME, "org.mcla.recomp.openbeta")


if __name__ == "__main__":
    unittest.main()
