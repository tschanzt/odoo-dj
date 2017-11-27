# -*- coding: utf-8 -*-
# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

import unicodecsv as csv
import io
import zipfile
import time
import datetime
from lxml import etree
from contextlib import contextmanager

from .slugifier import slugify

import odoo
ODOOVER = float(odoo.release.serie)

try:
    basestring
    PY2 = True
except NameError:
    PY2 = False
    basestring = str


def create_zipfile(files):
    in_mem_zip = io.BytesIO()
    with zipfile.ZipFile(in_mem_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath, data in files:
            # File "/usr/lib/python2.7/zipfile.py", line 1247, in writestr
            # TypeError: 'unicode' does not have the buffer interface
            if isinstance(data, str):
                data = data.encode('utf-8')
            # use info to keep date and set permissions
            info = zipfile.ZipInfo(
                filepath, date_time=time.localtime(time.time()))
            # set proper permissions
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    in_mem_zip.seek(0)
    return in_mem_zip


def make_title(name):
    dt = datetime.datetime.now().strftime('%Y%m%d_%H%M')
    return '{}-{}.zip'.format(slugify(name).replace('-', '_'), dt)


def csv_from_data(fields, rows):
    """Prepare data for CSV."""
    fp = io.BytesIO()
    writer = csv.writer(fp, quoting=csv.QUOTE_ALL, encoding='utf-8')
    writer.writerow(fields)
    for data in rows:
        row = []
        for i, col in enumerate(data):
            if col is False:
                col = None
            row.append(col)
        # writer.writerow([to_str(x, safe=True) for x in row])
        writer.writerow(row)

    fp.seek(0)
    data = fp.read()
    fp.close()
    return data


@contextmanager
def force_company(env, company_id):
    user_company = env.user.company_id
    env.user.update({'company_id': company_id})
    try:
        yield
    finally:
        env.user.update({'company_id': user_company})


def property_to_xmlid(env, val):
    """Convert property field value to xmlid."""
    model, res_id = val.split(',')
    return env[model].browse(int(res_id))._dj_export_xmlid()


def xmlid_to_property(env, val):
    """Inverse `property_to_xmlid` to get property value from xmlid."""
    record = env.ref(val)
    return '%s,%i' % (record._name, record.id)


def is_xml(content):
    """Check if given content is xml content."""
    try:
        etree.fromstring(content)
        return True
    except etree.XMLSyntaxError:
        return False


def context_to_string(ctx):
    """Convert context dictionary to a string.

    Keywords are sorted by alpha to always have the same order
    and ease output comparison.
    """
    out = []
    for k, v in ctx.items():
        out.append('{}={}'.format(k, v))
    return ', '.join(sorted(out))


def is_string(s):
    """Check this is a string in PY2 + PY3 compat way."""
    return isinstance(s, basestring)


def to_str(s, safe=False):
    """Compat layer py2/3. If `safe` Non-strings are returned as they are."""
    if safe and not is_string(s):
        # get it back safely
        return s
    if PY2:
        return s.encode('utf-8')
    # py3, str = unicode
    return s
