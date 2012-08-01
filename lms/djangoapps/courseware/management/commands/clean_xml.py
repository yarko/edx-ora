import os
import sys
import traceback

from filecmp import dircmp
from fs.osfs import OSFS
from path import path
from lxml import etree

from django.core.management.base import BaseCommand

from xmodule.modulestore.xml import XMLModuleStore
from xmodule.errortracker import make_error_tracker

def traverse_tree(course):
    '''Load every descriptor in course.  Return bool success value.'''
    queue = [course]
    while len(queue) > 0:
        node = queue.pop()
        queue.extend(node.get_children())

    return True


def export(course, export_dir):
    """Export the specified course to course_dir.  Creates dir if it doesn't exist.
    Overwrites files, does not clean out dir beforehand.
    """
    fs = OSFS(export_dir, create=True)
    if not fs.isdirempty('.'):
        print ('WARNING: Directory {dir} not-empty.'
               '  May clobber/confuse things'.format(dir=export_dir))

    try:
        xml = course.export_to_xml(fs)
        with fs.open('course.xml', mode='w') as f:
            f.write(xml)

        return True
    except:
        print 'Export failed!'
        traceback.print_exc()

    return False


def import_with_checks(course_dir, verbose=True):
    all_ok = True

    print "Attempting to load '{0}'".format(course_dir)

    course_dir = path(course_dir)
    data_dir = course_dir.dirname()
    course_dirs = [course_dir.basename()]

    (error_tracker, errors) = make_error_tracker()
    # No default class--want to complain if it doesn't find plugins for any
    # module.
    modulestore = XMLModuleStore(data_dir,
                   default_class=None,
                   eager=True,
                   course_dirs=course_dirs,
                   error_tracker=error_tracker)

    def str_of_err(tpl):
        (msg, exc_info) = tpl
        if exc_info is None:
            return msg

        exc_str = '\n'.join(traceback.format_exception(*exc_info))
        return '{msg}\n{exc}'.format(msg=msg, exc=exc_str)

    courses = modulestore.get_courses()
    if len(errors) != 0:
        all_ok = False
        print '\n'
        print "=" * 40
        print 'ERRORs during import:'
        print '\n'.join(map(str_of_err,errors))
        print "=" * 40
        print '\n'

    n = len(courses)
    if n != 1:
        print 'ERROR: Expect exactly 1 course.  Loaded {n}: {lst}'.format(
            n=n, lst=courses)
        return (False, None)

    course = courses[0]

    #print course
    validators = (
        traverse_tree,
        )

    print "=" * 40
    print "Running validators..."

    for validate in validators:
        print 'Running {0}'.format(validate.__name__)
        all_ok = validate(course) and all_ok


    if all_ok:
        print 'Course passes all checks!'
    else:
        print "Course fails some checks.  See above for errors."
    return all_ok, course


def check_roundtrip(course_dir):
    '''Check that import->export leaves the course the same'''

    print "====== Roundtrip import ======="
    (ok, course) = import_with_checks(course_dir)
    if not ok:
        raise Exception("Roundtrip import failed!")

    print "====== Roundtrip export ======="
    export_dir = course_dir + ".rt"
    export(course, export_dir)

    # dircmp doesn't do recursive diffs.
    # diff = dircmp(course_dir, export_dir, ignore=[], hide=[])
    print "======== Roundtrip diff: ========="
    sys.stdout.flush()  # needed to make diff appear in the right place
    os.system("diff -r {0} {1}".format(course_dir, export_dir))
    print "======== ideally there is no diff above this ======="


def clean_xml(course_dir, export_dir):
    (ok, course) = import_with_checks(course_dir)
    if ok:
        export(course, export_dir)
        check_roundtrip(export_dir)
    else:
        print "Did NOT export"



class Command(BaseCommand):
    help = """Imports specified course.xml, validate it, then exports in
    a canonical format.

Usage: clean_xml PATH-TO-COURSE-DIR PATH-TO-OUTPUT-DIR
"""
    def handle(self, *args, **options):
        if len(args) != 2:
            print Command.help
            return

        clean_xml(args[0], args[1])