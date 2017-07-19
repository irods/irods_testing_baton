from __future__ import print_function

import errno
import json
import logging
import multiprocessing
import optparse
import os
import shutil
import socket
import sys

import irods_python_ci_utilities


def build(baton_git_repository, baton_git_commitish, output_root_directory):
    install_building_dependencies()
    baton_source_dir = build_baton(baton_git_repository, baton_git_commitish, output_root_directory)
    configure_irods_for_baton_tests()
    try:
        run_baton_tests(baton_source_dir)
    finally:
        if output_root_directory:
            copy_test_results(baton_source_dir, output_root_directory)

def install_building_dependencies():
    dispatch_map = {
        'Ubuntu': install_building_dependencies_apt,
    }
    try:
        return dispatch_map[irods_python_ci_utilities.get_distribution()]()
    except KeyError:
        irods_python_ci_utilities.raise_not_implemented_for_distribution()

def install_building_dependencies_apt():
    irods_python_ci_utilities.install_os_packages(['autoconf', 'libtool', 'pkg-config', 'libjansson-dev', 'libssl-dev', 'libstdc++-4.8-dev', 'make', 'check'])

def build_baton(baton_git_repository, baton_git_commitish, output_root_directory):
    baton_source_dir = irods_python_ci_utilities.git_clone(baton_git_repository, baton_git_commitish)
    logging.getLogger(__name__).info('Using baton source directory: %s', baton_source_dir)
    irods_python_ci_utilities.subprocess_get_output(['autoreconf', '-i'], cwd=baton_source_dir, check_rc=True)
    try:
        irods_python_ci_utilities.subprocess_get_output([os.path.join(baton_source_dir, 'configure'), '--with-irods'], cwd=baton_source_dir, check_rc=True)
    finally:
        if output_root_directory:
            irods_python_ci_utilities.mkdir_p(output_root_directory)
            irods_python_ci_utilities.copy_file_if_exists(os.path.join(baton_source_dir, 'config.log'), output_root_directory)
    irods_python_ci_utilities.subprocess_get_output(['make', '-j', str(multiprocessing.cpu_count())], cwd=baton_source_dir, check_rc=True)
    return baton_source_dir

def configure_irods_for_baton_tests():
    create_local_irods_environment_file()
    create_local_irods_password_file()
    create_test_resource()
    change_server_hash_scheme_to_md5()

def create_local_irods_environment_file():
    contents = {
        "irods_host": socket.gethostname(),
        "irods_port": 1247,
        "irods_user_name": "rods",
        "irods_zone_name": "tempZone",
        "irods_default_hash_scheme": "MD5"
    }
    irods_python_ci_utilities.mkdir_p(os.path.expanduser('~/.irods'))
    with open(os.path.expanduser('~/.irods/irods_environment.json'), 'w') as f:
        json.dump(contents, f, ensure_ascii=True, sort_keys=True, indent=4)

def create_local_irods_password_file():
    irods_python_ci_utilities.subprocess_get_output(['iinit', 'rods'], check_rc=True)

def create_test_resource():
    irods_python_ci_utilities.subprocess_get_output(['iadmin', 'mkresc', 'testResc', 'unixfilesystem', '{0}:/var/lib/irods/testRescVault'.format(socket.gethostname())], check_rc=True)

def change_server_hash_scheme_to_md5():
    server_config_path = '/etc/irods/server_config.json'
    irods_python_ci_utilities.subprocess_get_output(['sudo', 'chmod', 'o+rw', server_config_path], check_rc=True)
    with open(server_config_path) as f:
        d = json.load(f)
    d['default_hash_scheme'] = 'MD5'
    with open(server_config_path, 'w') as f:
        json.dump(d, f, ensure_ascii=True, sort_keys=True, indent=4)

def run_baton_tests(baton_source_dir):
    env = os.environ.copy()
    env['CK_DEFAULT_TIMEOUT'] = '20' # the 'check' unit test framework has a default timeout that is too short for three of the baton tests. If you see 'Test timeout expired', may need to increase this
    irods_python_ci_utilities.subprocess_get_output(['make', 'check'], env=env, cwd=baton_source_dir, check_rc=True)

def copy_test_results(baton_source_dir, output_root_directory):
    irods_python_ci_utilities.mkdir_p(output_root_directory)
    irods_python_ci_utilities.copy_file_if_exists(os.path.join(baton_source_dir, 'tests', 'check_baton.log'), output_root_directory)

def main():
    parser = optparse.OptionParser()
    parser.add_option('--baton_git_commitish')
    parser.add_option('--baton_git_repository')
    parser.add_option('--output_root_directory')
    parser.add_option('--just_install_dependencies', action='store_true', default=False)
    parser.add_option('--verbose', action='store_true', default=False)
    options, _ = parser.parse_args()

    if options.verbose:
        irods_python_ci_utilities.register_logging_stream_handler(sys.stdout, logging.INFO)

    if options.just_install_dependencies:
        install_building_dependencies()
        return

    if not options.baton_git_repository:
        print('--baton_git_repository must be provided', file=sys.stderr)
        sys.exit(1)

    if not options.baton_git_commitish:
        print('--baton_git_commitish must be provided', file=sys.stderr)
        sys.exit(1)

    build(options.baton_git_repository, options.baton_git_commitish, options.output_root_directory)

if __name__ == '__main__':
    main()
