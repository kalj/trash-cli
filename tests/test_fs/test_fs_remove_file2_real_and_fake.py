import pytest

from tests.support.put.real_and_fake_env import env, real_and_fake
from trashcli.fslib.fs_remove_file2 import FsRemoveFile2

env = env  # the fixture, imported from its module


@pytest.fixture(autouse=True)
def trash_dir(env):
    env.fs.mkdirs(env.path('Trash'))


def home_trash(env):
    # FsRemoveFile2 only adds permissions inside the home trash
    return {'HOME': env.base, 'XDG_DATA_HOME': env.base}


def remove_file2(env, path):
    FsRemoveFile2(env.fs, home_trash(env), lambda: 1000).remove_file2(path)


# FsRemoveFile2 is what trash-empty and trash-rm use to delete a trashed
# file or dir for good.
class TestFsRemoveFile2:
    @real_and_fake()
    def test_removes_a_file(self, env):
        env.fs.write_file(env.path('Trash/file'), 'a')

        remove_file2(env, env.path('Trash/file'))

        assert env.fs.path_lexists(env.path('Trash/file')) is False

    @real_and_fake()
    def test_removes_a_dir_with_its_content(self, env):
        env.fs.mkdirs(env.path('Trash/dir/subdir'))
        env.fs.write_file(env.path('Trash/dir/subdir/file'), 'a')

        remove_file2(env, env.path('Trash/dir'))

        assert env.fs.path_lexists(env.path('Trash/dir')) is False

    @real_and_fake()
    def test_removes_a_symlink_to_a_dir_not_the_dir(self, env):
        env.fs.mkdirs(env.path('Trash/dir'))
        env.fs.write_file(env.path('Trash/dir/file'), 'a')
        env.fs.symlink(env.path('Trash/dir'), env.path('Trash/link'))

        remove_file2(env, env.path('Trash/link'))

        assert env.fs.path_lexists(env.path('Trash/link')) is False
        assert env.fs.path_lexists(env.path('Trash/dir/file')) is True

    @real_and_fake()
    def test_fails_on_a_missing_path(self, env):
        with pytest.raises(OSError):
            remove_file2(env, env.path('Trash/missing'))


# https://github.com/andreafrancia/trash-cli/issues/364
# A trashed dir can contain read-only dirs (e.g. the Go module cache): they
# cannot be emptied as they are, so the dirs being removed are made writable.
class TestFsRemoveFile2OnReadOnlyDirs:
    @real_and_fake()
    def test_removes_a_dir_containing_a_read_only_subdir(self, env):
        env.fs.mkdirs(env.path('Trash/dir/subdir'))
        env.fs.write_file(env.path('Trash/dir/subdir/file'), 'a')
        env.fs.chmod(env.path('Trash/dir/subdir'), 0o555)

        remove_file2(env, env.path('Trash/dir'))

        assert env.fs.path_lexists(env.path('Trash/dir')) is False

    @real_and_fake()
    def test_removes_a_read_only_dir_with_content(self, env):
        env.fs.mkdirs(env.path('Trash/dir/a/b'))
        env.fs.write_file(env.path('Trash/dir/a/b/file'), 'a')
        env.fs.chmod(env.path('Trash/dir/a/b'), 0o555)
        env.fs.chmod(env.path('Trash/dir/a'), 0o555)
        env.fs.chmod(env.path('Trash/dir'), 0o555)

        remove_file2(env, env.path('Trash/dir'))

        assert env.fs.path_lexists(env.path('Trash/dir')) is False

    @real_and_fake()
    def test_removes_a_dir_with_a_subdir_that_has_no_search_permission(self, env):
        env.fs.mkdirs(env.path('Trash/dir/subdir'))
        env.fs.write_file(env.path('Trash/dir/subdir/file'), 'a')
        env.fs.chmod(env.path('Trash/dir/subdir'), 0o400)

        remove_file2(env, env.path('Trash/dir'))

        assert env.fs.path_lexists(env.path('Trash/dir')) is False

    @real_and_fake()
    def test_does_not_change_the_permissions_of_a_symlink_target(self, env):
        # a symlink inside the trashed dir can point outside the trash
        env.fs.mkdirs(env.path('Trash/outside'))
        env.fs.chmod(env.path('Trash/outside'), 0o555)
        env.fs.mkdirs(env.path('Trash/dir/subdir'))
        env.fs.symlink(env.path('Trash/outside'), env.path('Trash/dir/subdir/link'))
        env.fs.chmod(env.path('Trash/dir/subdir'), 0o555)

        try:
            remove_file2(env, env.path('Trash/dir'))

            assert env.fs.path_lexists(env.path('Trash/dir')) is False
            assert env.fs.get_mod(env.path('Trash/outside')) == 0o555
        finally:
            env.fs.chmod(env.path('Trash/outside'), 0o755)

    @real_and_fake()
    def test_does_not_change_the_permissions_of_the_parent(self, env):
        env.fs.mkdirs(env.path('Trash/parent/dir/subdir'))
        env.fs.write_file(env.path('Trash/parent/dir/subdir/file'), 'a')
        env.fs.chmod(env.path('Trash/parent/dir/subdir'), 0o555)
        env.fs.chmod(env.path('Trash/parent'), 0o555)

        try:
            with pytest.raises(OSError):
                remove_file2(env, env.path('Trash/parent/dir'))

            assert env.fs.get_mod(env.path('Trash/parent')) == 0o555
        finally:
            env.fs.chmod(env.path('Trash/parent'), 0o755)
            env.fs.chmod(env.path('Trash/parent/dir'), 0o755)
            if env.fs.path_lexists(env.path('Trash/parent/dir/subdir')):
                env.fs.chmod(env.path('Trash/parent/dir/subdir'), 0o755)

    @real_and_fake()
    def test_does_not_read_an_unreadable_dir(self, env):
        # only the permissions needed to unlink are added, not the read one
        env.fs.mkdirs(env.path('Trash/dir/subdir'))
        env.fs.write_file(env.path('Trash/dir/subdir/file'), 'a')
        env.fs.chmod(env.path('Trash/dir/subdir'), 0o300)

        try:
            with pytest.raises(OSError):
                remove_file2(env, env.path('Trash/dir'))

            assert env.fs.path_lexists(env.path('Trash/dir/subdir/file')) is True
        finally:
            env.fs.chmod(env.path('Trash/dir/subdir'), 0o700)

    @real_and_fake()
    def test_leaves_writable_dirs_unchanged_when_it_fails(self, env):
        # the permissions are changed only where it is needed
        env.fs.mkdirs(env.path('Trash/dir/subdir'))
        env.fs.write_file(env.path('Trash/dir/subdir/file'), 'a')
        env.fs.chmod(env.path('Trash/dir/subdir'), 0o300)
        env.fs.chmod(env.path('Trash/dir'), 0o750)

        try:
            with pytest.raises(OSError):
                remove_file2(env, env.path('Trash/dir'))

            assert env.fs.get_mod(env.path('Trash/dir')) == 0o750
        finally:
            env.fs.chmod(env.path('Trash/dir/subdir'), 0o700)

    @real_and_fake()
    def test_restores_the_permissions_it_added_when_it_fails(self, env):
        # the dirs that survive a failure are left as they were found
        env.fs.mkdirs(env.path('Trash/dir/a/unreadable'))
        env.fs.write_file(env.path('Trash/dir/a/unreadable/file'), 'a')
        env.fs.chmod(env.path('Trash/dir/a/unreadable'), 0o300)
        env.fs.chmod(env.path('Trash/dir/a'), 0o555)
        env.fs.chmod(env.path('Trash/dir'), 0o555)

        try:
            with pytest.raises(OSError):
                remove_file2(env, env.path('Trash/dir'))

            assert env.fs.get_mod(env.path('Trash/dir')) == 0o555
            assert env.fs.get_mod(env.path('Trash/dir/a')) == 0o555
            assert env.fs.get_mod(env.path('Trash/dir/a/unreadable')) == 0o300
        finally:
            env.fs.chmod(env.path('Trash/dir'), 0o755)
            env.fs.chmod(env.path('Trash/dir/a'), 0o755)
            env.fs.chmod(env.path('Trash/dir/a/unreadable'), 0o755)
