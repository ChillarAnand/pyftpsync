# -*- coding: UTF-8 -*-
"""
Tests for pyftpsync
"""
from __future__ import print_function

from ftplib import FTP
from pprint import pprint
from unittest import TestCase
import unittest

from ftpsync.ftp_target import *  # @UnusedWildImport
from ftpsync.targets import *  # @UnusedWildImport

from ftpsync.synchronizers import DownloadSynchronizer, UploadSynchronizer, \
    BiDirSynchronizer
from test.test_flow import prepare_fixtures, PYFTPSYNC_TEST_FTP_URL, \
    PYFTPSYNC_TEST_FOLDER, _get_test_file_date, STAMP_20140101_120000, \
    _set_test_file_date, _empty_folder, _write_test_file

DO_BENCHMARKS = False #True

#===============================================================================
# Module setUp / tearDown
#===============================================================================
def setUpModule():
    pass

def tearDownModule():
    pass


#===============================================================================
# FtpTest
#===============================================================================
class FtpTest(TestCase):                          
    """Test basic ftplib.FTP functionality."""
    def setUp(self):
        # Remote URL, e.g. "ftp://user:password@example.com/my/test/folder"
        ftp_url = PYFTPSYNC_TEST_FTP_URL
        if not ftp_url:
            self.skipTest("Must configure a FTP target (environment variable PYFTPSYNC_TEST_FTP_URL)")

        parts = urlparse(ftp_url, allow_fragments=False)
        self.assertEqual(parts.scheme.lower(), "ftp")
        host = parts.netloc.split("@", 1)[1]
        self.PATH = parts.path
        self.ftp = FTP()
#        self.ftp.debug(1) 
        self.ftp.connect(host)
        self.ftp.login(parts.username, parts.password)

    def tearDown(self):
#        self.ftp.abort()
#        self.ftp.close()
        self.ftp.quit()
        del self.ftp
        
    def test_ftp(self):
        ftp = self.ftp
        self.assertEqual(ftp.pwd(), "/")
        ftp.cwd(self.PATH)
        self.assertEqual(ftp.pwd(), self.PATH)
        res = ftp.nlst()
        print(res)
        res = ftp.dir()
        print(res)

    def test_mlsd(self):
        ftp = self.ftp
        self.assertEqual(ftp.pwd(), "/")
        ftp.cwd(self.PATH)
        self.assertEqual(ftp.pwd(), self.PATH)
        
        def adder(line):
            print(line)
        ftp.retrlines("MLSD", adder)
#        dir = FTPDirectory(self.PATH)
#        dir.getdata(ftp)
#        for f in dir.walk():
#            print(f)

#===============================================================================
# FtpTargetTest
#===============================================================================
class FtpTargetTest(TestCase):                          
    """Test ftp_target.FtpTarget functionality."""
    def setUp(self):
        # Remote URL, e.g. "ftp://user:password@example.com/my/test/folder"
        ftp_url = PYFTPSYNC_TEST_FTP_URL
        if not ftp_url:
            self.skipTest("Must configure a FTP target (environment variable PYFTPSYNC_TEST_FTP_URL)")
        self.assertTrue("/test" in ftp_url or "/temp" in ftp_url, "FTP target path must include '/test' or '/temp'")

        # Create local /temp1 folder with files and empty /temp2 folder
        prepare_fixtures()

#        print(ftp_url)
        
        parts = urlparse(ftp_url, allow_fragments=False)
        self.assertEqual(parts.scheme.lower(), "ftp")
#        print(parts)
#        self.creds = parts.username, parts.password
#        self.HOST = parts.netloc.split("@", 1)[1]
        self.PATH = parts.path
#        user, passwd = get_stored_credentials("pyftpsync.pw", self.HOST)

        self.remote = make_target(ftp_url)
        self.remote.open()
        # This check is already preformed in the constructor:
#        self.assertEqual(self.remote.pwd(), self.PATH)

        # Delete all files in remote target folder
        self.remote._rmdir_impl(".", keep_root=True)

    def tearDown(self):
        self.remote.close()
        del self.remote

    def test_remote(self):
        remote = self.remote
        
        self.assertEqual(remote.pwd(), self.PATH)

        remote.cwd(self.PATH)
        self.assertEqual(remote.pwd(), self.PATH)

        self.assertRaises(RuntimeError, remote.cwd, "..")
        self.assertEqual(remote.pwd(), self.PATH)
        
        
    def test_readwrite(self):
        remote = self.remote
        
        if sys.version_info[0] < 3:
            # 'abc_äöü_ß¿€'
            b = 'abc_\xc3\xa4\xc3\xb6\xc3\xbc_\xc3\x9f\xc2\xbf\xe2\x82\xac'
            u = b.decode("utf8")
        else:
            u = "abc_äöü_¿ß"
        s = u.encode("utf8")

        remote.write_text("write_test_u.txt", u)
        self.assertEqual(remote.read_text("write_test_u.txt"), u)

        remote.write_text("write_test_s.txt", s)
        self.assertEqual(remote.read_text("write_test_s.txt"), u)

    def test_json(self):
        remote = self.remote

        d = {"a": 1, "b": 2, "sub": {"x": 10, "y": 11}}
        pprint(d)
        if sys.version_info[0] == 2:
            s = json.dumps(d, indent=4, sort_keys=True)
            b = io.BytesIO(s) 
        else:
            buf = io.StringIO()
            json.dump(d, buf, indent=4, sort_keys=True)
    #        print(buf.getvalue())
            buf.flush()
            buf.seek(0)
            while 1:
                s = buf.readline()
                if not s: break
                print("%r" % s)
            buf.seek(0)
            print(buf.getvalue())
            b = io.BytesIO(bytes(buf.getvalue(), "utf8")) 
        res = remote.ftp.storlines("STOR " + "meta.json", b)
        print(res)

#     def test_download_fs_ftp(self):
#         local = FsTarget(os.path.join(PYFTPSYNC_TEST_FOLDER, "temp1"))
#         remote = self.remote
#         opts = {"force": False, "delete": False}
#         s = DownloadSynchronizer(local, remote, opts)
#         s.run()
#         stats = s.get_stats()
#         pprint(stats)
# #        self.assertEqual(stats["source_files"], 1)


    def test_sync_fs_ftp(self):
        local = FsTarget(os.path.join(PYFTPSYNC_TEST_FOLDER, "temp1"))
        remote = self.remote
        
        # Upload all of /temp1 to remote
        
        opts = {"force": False, "delete": True, "verbose": 3, "dry_run": False}
        s = UploadSynchronizer(local, remote, opts)
        s.run()
        
        stats = s.get_stats()
#        pprint(stats)

        self.assertEqual(stats["local_dirs"], 2)
        self.assertEqual(stats["local_files"], 4) # currently files are not counted, when inside a *new* folder
        self.assertEqual(stats["remote_dirs"], 0)
        self.assertEqual(stats["remote_files"], 0)
        self.assertEqual(stats["files_written"], 6)
        self.assertEqual(stats["dirs_created"], 2)
        self.assertEqual(stats["bytes_written"], 16403)
        
        # Change one file and upload again
        
        _set_test_file_date("temp1/file1.txt")

        opts = {"force": False, "delete": True, "verbose": 3, "dry_run": False}
        s = UploadSynchronizer(local, remote, opts)
        s.run()
        stats = s.get_stats()
#        pprint(stats)

        self.assertEqual(stats["entries_seen"], 18) # ???
        self.assertEqual(stats["entries_touched"], 1)
        self.assertEqual(stats["files_created"], 0)
        self.assertEqual(stats["files_deleted"], 0)
        self.assertEqual(stats["files_written"], 1)
        self.assertEqual(stats["dirs_created"], 0)
        self.assertEqual(stats["download_files_written"], 0)
        self.assertEqual(stats["upload_files_written"], 1)
        self.assertEqual(stats["conflict_files"], 0)
        self.assertEqual(stats["bytes_written"], 3)
        
        # Download all from remote to /temp2
        
        local = FsTarget(os.path.join(PYFTPSYNC_TEST_FOLDER, "temp2"))

        opts = {"force": False, "delete": True, "verbose": 3, "dry_run": False}
        s = DownloadSynchronizer(local, remote, opts)
        s.run()
        stats = s.get_stats()
#        pprint(stats)

        self.assertEqual(stats["entries_seen"], 8)
        self.assertEqual(stats["entries_touched"], 8)
#        self.assertEqual(stats["files_created"], 6)
        self.assertEqual(stats["files_deleted"], 0)
        self.assertEqual(stats["files_written"], 6)
        self.assertEqual(stats["dirs_created"], 2)
        self.assertEqual(stats["download_files_written"], 6)
        self.assertEqual(stats["upload_files_written"], 0)
        self.assertEqual(stats["conflict_files"], 0)
        self.assertEqual(stats["bytes_written"], 16403)

        # Original file times are preserved, even when retrieved from FTP
        
        self.assertNotEqual(_get_test_file_date("temp1/file1.txt"), STAMP_20140101_120000)
        self.assertEqual(_get_test_file_date("temp1/file1.txt"), _get_test_file_date("temp2/file1.txt"))

        self.assertEqual(_get_test_file_date("temp1/file2.txt"), STAMP_20140101_120000)
        self.assertEqual(_get_test_file_date("temp2/file2.txt"), STAMP_20140101_120000)

        # Synchronize /temp1 <=> remote : nothing to do
        
        local = FsTarget(os.path.join(PYFTPSYNC_TEST_FOLDER, "temp1"))

        opts = {"verbose": 3, "dry_run": False}
        s = BiDirSynchronizer(local, remote, opts)
        s.run()
        stats = s.get_stats()
        pprint(stats)
        self.assertEqual(stats["entries_touched"], 0)
        self.assertEqual(stats["conflict_files"], 0)
        self.assertEqual(stats["bytes_written"], 0)

        # Synchronize /temp2 <=> remote : nothing to do
        
        local = FsTarget(os.path.join(PYFTPSYNC_TEST_FOLDER, "temp2"))

        opts = {"verbose": 3, "dry_run": False}
        s = BiDirSynchronizer(local, remote, opts)
        s.run()
        stats = s.get_stats()
        pprint(stats)
        self.assertEqual(stats["entries_touched"], 0)
        self.assertEqual(stats["conflict_files"], 0)
        self.assertEqual(stats["bytes_written"], 0)


#===============================================================================
# BenchmarkTest
#===============================================================================
class BenchmarkTest(TestCase):                          
    """Test ftp_target.FtpTarget functionality."""
    def setUp(self):
        if not DO_BENCHMARKS:
            self.skipTest("DO_BENCHMARKS is not set")
        # Remote URL, e.g. "ftp://user:password@example.com/my/test/folder"
        ftp_url = PYFTPSYNC_TEST_FTP_URL
        if not ftp_url:
            self.skipTest("Must configure a FTP target (environment variable PYFTPSYNC_TEST_FTP_URL)")
        self.assertTrue("/test" in ftp_url or "/temp" in ftp_url, "FTP target path must include '/test' or '/temp'")

        # Create local /temp1 folder with files and empty /temp2 folder
        prepare_fixtures()

        self.remote = make_target(ftp_url)
        self.remote.open()
        # Delete all files in remote target folder
        self.remote._rmdir_impl(".", keep_root=True)

    def tearDown(self):
        self.remote.close()
        del self.remote

    def _transfer_files(self, count, size):
        temp1_path = os.path.join(PYFTPSYNC_TEST_FOLDER, "temp1")
        _empty_folder(temp1_path) # remove standard test files 

        local = FsTarget(temp1_path)
        remote = self.remote
        
        for i in range(count):
            _write_test_file("temp1/file_%s.txt" % i, size=size)

        # Upload all of /temp1 to remote
        
        opts = {"force": False, "delete": False, "verbose": 3, "dry_run": False}
        s = UploadSynchronizer(local, remote, opts)
        s.run()
        stats = s.get_stats()
#        pprint(stats)

        self.assertEqual(stats["files_written"], count)
        self.assertEqual(stats["bytes_written"], count * size)
#        pprint(stats)
        print("Upload %s x %s bytes took %s: %s" % (count, size, stats["upload_write_time"], stats["upload_rate_str"]), file=sys.stderr)

        # Download all of remote to /temp2
        
        local = FsTarget(os.path.join(PYFTPSYNC_TEST_FOLDER, "temp2"))

        opts = {"force": False, "delete": True, "verbose": 3, "dry_run": False}
        s = DownloadSynchronizer(local, remote, opts)
        s.run()
        stats = s.get_stats()
#        pprint(stats)

        self.assertEqual(stats["files_written"], count)
        self.assertEqual(stats["bytes_written"], count * size)

#        pprint(stats)
        print("Download %s x %s bytes took %s: %s" % (count, size, stats["download_write_time"], stats["download_rate_str"]), file=sys.stderr)

    def test_transfer_small_files(self):
        """Transfer 20 KiB in many small files."""
        self._transfer_files(count=10, size=2*1024)

    def test_transfer_large_files(self):
        """Transfer 20 KiB in one large file."""
        self._transfer_files(count=1, size=20*1024)

#===============================================================================
# PlainTest
#===============================================================================
class PlainTest(TestCase):
    """Tests that don't connect."""
    def setUp(self):
#        user, passwd = get_stored_credentials("pyftpsync.pw", self.HOST)
        pass
    
    def tearDown(self):
        pass

    def test_make_target(self):
        t = make_target("ftp://ftp.example.com/target/folder")
        self.assertTrue(isinstance(t, FtpTarget))
        self.assertEqual(t.host, "ftp.example.com")
        self.assertEqual(t.root_dir, "/target/folder")
        self.assertEqual(t.username, None)
        # scheme is case-insensitive
        t = make_target("FTP://ftp.example.com/target/folder")
        self.assertTrue(isinstance(t, FtpTarget))
        
        # pass credentials wit URL
        t = make_target("ftp://user:secret@ftp.example.com/target/folder")
        self.assertTrue(isinstance(t, FtpTarget))
        self.assertEqual(t.host, "ftp.example.com")
        self.assertEqual(t.username, "user")
        self.assertEqual(t.password, "secret")
        self.assertEqual(t.root_dir, "/target/folder")

        t = make_target("ftp://www.user.com:secret@ftp.example.com/target/folder")
        self.assertTrue(isinstance(t, FtpTarget))
        self.assertEqual(t.username, "www.user.com")
        self.assertEqual(t.password, "secret")
        self.assertEqual(t.root_dir, "/target/folder")

        # unsupported schemes
        self.assertRaises(ValueError, make_target, "http://example.com/test")
        self.assertRaises(ValueError, make_target, "https://example.com/test")


#===============================================================================
# Main
#===============================================================================
if __name__ == "__main__":
    unittest.main()

#     print(sys.version)
#     suite = unittest.TestSuite()
# #    suite.addTest(FtpTest("test_upload_fs_fs"))
# #    suite.addTest(FtpTest("test_download_fs_fs"))
#     suite.addTest(FtpTest("test_upload_fs_ftp"))
#     suite.addTest(FtpTest("test_download_fs_ftp"))
# #    suite.addTest(PlainTest("test_json"))
# #    suite.addTest(PlainTest("test_make_target"))
# #    suite.addTest(FtpTest("test_readwrite"))
#     unittest.TextTestRunner(verbosity=1).run(suite)
