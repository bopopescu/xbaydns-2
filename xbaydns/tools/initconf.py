#!/usr/bin/env python
# encoding: utf-8
"""
initconf.py

Created by 黄 冬 on 2007-11-19.
Copyright (c) 2007 xBayDNS Team. All rights reserved.

初始化bind的配置文件。运行这个程序需要root的权限。不管你是什么操作系统，它的初始化都是将
/etc/namedb
目录进行初始化
"""
from xbaydns.utils import shtools
from xbaydns.conf import sysconf

import errno
import getopt
import logging.config
import os
import pwd
import sys
from tempfile import mkdtemp
import time

log = logging.getLogger('xbaydns.tools.initconf')

BASEDIR = sysconf.installdir
TMPL_DIR = BASEDIR + "/tools/templates"
log.debug("template diris:%s"%TMPL_DIR)
TMPL_DEFAULTZONE = "%s/defaultzone.tmpl"%TMPL_DIR
TMPL_NAMEDCONF = "%s/namedconf.tmpl"%TMPL_DIR
TMPL_NAMEDROOT = "%s/namedroot.tmpl"%TMPL_DIR
ERR_BACKUP = 1000



def acl_file(acls):
    '''
安dict的输入生成named所需要的acl字符串
acls = dict(aclname=('ip0', 'net0'))
    '''
    acl_content = ""
    for aclname, aclvalue in acls.iteritems():
        acl_content += 'acl "%s" { '%aclname
        for aclnet in aclvalue:
            acl_content += "%s; "%aclnet
        acl_content += "};\n"
    return acl_content

def defaultzone_file():
    """得到缺省的zone文件，也就是模板目录中的defaultzone.tmpl文件内容"""
    if os.path.isfile(TMPL_DEFAULTZONE) == False:
        return False
    else:
        tmpl_file = open(TMPL_DEFAULTZONE, "r")
        defzone = tmpl_file.read() + "\n"
        tmpl_file.close()
        return defzone

def named_root_file():
    """得到缺省的root文件，也就是模板目录中的namedroot.tmpl文件内容"""
    if os.path.isfile(TMPL_NAMEDROOT) == False:
        return False
    else:
        tmpl_file = open(TMPL_NAMEDROOT, "r")
        named_root = tmpl_file.read()
        tmpl_file.close()
        return named_root

def namedconf_file(include_files):
    """通过namedconf.tmpl生成最终的named.conf文件。include_file为一个dic，每项的值为一个要include的文件路径"""
    if os.path.isfile(TMPL_DEFAULTZONE) == False:
        return False
    else:
        tmpl_file = open(TMPL_NAMEDCONF, "r")
        namedconf = tmpl_file.read() + "\n"
        tmpl_file.close()
        for filename in include_files.itervalues():
            namedconf += 'include "%s";\n'%filename
        return namedconf + "\n"

def make_localhost():
    pass
    
def backup_conf(real_confdir, real_dbdir, backdir):
    """备份named.conf和namedb目录。read_confdir为包含named.conf的目录，real_dbdir为包含zone db的目录，backdir为备份文件存放的目录。"""
    if os.path.isdir(real_confdir) == False:
        return False
    else:
        time_suffix = time.strftime("%y%m%d%H%M")
        retcode = shtools.execute(executable = "tar", args = "-cjf %s/namedconf_%s.tar.bz2 %s"%(backdir,  time_suffix, real_confdir))
        if retcode == 0:
            retcode = shtools.execute(executable = "tar", args = "-cjf %s/namedb_%s.tar.bz2 %s"%(backdir,  time_suffix, real_dbdir))
            if retcode == 0:
                return True
    return False

def create_destdir(named_uid):
    """创建系统目录，这里只是在tmp目录中建立"""
    tmpdir = mkdtemp()
    os.makedirs("%s/namedconf/acl"%tmpdir)
    os.makedirs("%s/namedb/dynamic"%tmpdir)
    os.chown("%s/namedb/dynamic"%tmpdir, named_uid, 0)
    os.mkdir("%s/namedb/master"%tmpdir)
    os.mkdir("%s/namedb/slave"%tmpdir)
    os.chown("%s/namedb/slave"%tmpdir, named_uid, 0)
    return tmpdir

def create_conf(tmpdir):
    """在tmpdir目录中创建配置文件"""
    acl = acl_file(sysconf.default_acl)
    defzone = defaultzone_file()
    namedroot = named_root_file()

    if acl == False or defzone == False or namedroot == False:
        return False
    else:
        tmpfile = open("%s/namedconf/%s"%(tmpdir, sysconf.filename_map['acl']), "w")
        tmpfile.write(acl)
        tmpfile.close()
        tmpfile = open("%s/namedconf/%s"%(tmpdir, sysconf.filename_map['defzone']), "w")
        tmpfile.write(defzone)
        tmpfile.close()
        tmpfile = open("%s/namedconf/named.root"%tmpdir, "w")
        tmpfile.write(namedroot)
        tmpfile.close()
        namedconf = namedconf_file(sysconf.filename_map)
        tmpfile = open("%s/namedconf/named.conf"%tmpdir, "w")
        tmpfile.write(namedconf)
        tmpfile.close()
        return True
        
def install_conf(tmpdir, real_confdir, real_dbdir):
    """将tmpdir中的临时文件安装到最终的使用目录中去"""
    ret = shtools.execute(executable="rm", args="-rf %s %s"%(real_confdir, real_dbdir))
    if ret == 0:
        ret = shtools.execute(executable="mkdir", args="-p %s %s"%(real_confdir, real_dbdir))
        if ret == 0:
            ret = shtools.execute(executable="cp", args="-R %s/namedconf/ %s"%(tmpdir, real_confdir))
            if ret == 0:
                ret = shtools.execute(executable="cp", args="-R %s/namedb/ %s"%(tmpdir, real_dbdir))
                if ret == 0:
                    ret = shtools.execute(executable="rm", args="-rf %s"%tmpdir)
                    if ret == 0:
                        return True
    else:
        return False
    
def usage():
    print "usage: %s [-dbc]"%__file__
    
def main():
    # check root
    if os.getuid() != 0:
        print "You need be root to run this program."
        return errno.EPERM
    # parse options
    try:
        opts = getopt.getopt(sys.argv[1:], "d:b:c:")
    except getopt.GetoptError:
        usage()
        return errno.EINVAL
    confdir = sysconf.namedconf
    dbdir = sysconf.nameddb
    backup = False
    backdir = ""
    for optname, optval in opts[0]:
        if optname == "-c":
            confdir = optval
        elif optname == "-d":
            dbdir = optval
        elif optname == "-b":
            backup = True
            backdir = optval
    real_confdir = os.path.realpath(confdir)
    real_dbdir = os.path.realpath(dbdir)
    # backup
    if backup == True:
        if os.path.isdir(real_confdir) == True and os.path.isdir(real_dbdir) == True:
            ret = backup_conf(real_confdir, real_dbdir, backdir)
            if ret == False:
                print "Backup failed."
                return -1
        else:
            print "No namedb in basedir, I'll continue."
    # that's my business
    # get named uid
    ostype = os.uname()[0].lower()
    try:
        named_user = sysconf.named_user_map[ostype]
    except KeyError:
        print "This program doesn't support your os. Assumed user 'bind'."
        named_user = "bind"
    try:
        named_uid = pwd.getpwnam(named_user)[2]
    except KeyError:
        print "No such a user %s. I'll exit."%named_user
        return errno.EINVAL
    tmpdir = create_destdir(named_uid)
    log.debug(tmpdir)
    if create_conf(tmpdir) == False or install_conf(tmpdir, real_confdir, real_dbdir) == False:
        print "Create configuration files failed."
        return -1
    else:
        return 0

if __name__ == '__main__':
    sys.exit(main())
