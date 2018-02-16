# -*- coding: utf-8 -*-
# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, tools
import os
import codecs
import mimetypes
import hashlib

from ..utils import is_xml, to_str, is_string
from ..slugifier import slugify


def encode64(content):
    return codecs.encode(content, 'base64')


def decode64(content):
    return codecs.decode(content, 'base64')


class Base(models.AbstractModel):

    _inherit = 'base'

    @staticmethod
    def _hash_them(atuple):
        """Return always the same hashed string for given tuple."""
        # TODO: get a shorter but still unique hash
        # Maybe using `hashids` lib?
        return hashlib.md5(str(atuple).encode()).hexdigest()

    def _dj_xmlid_export_module(self):
        """Customize module name for dj compilation.

        By default is `__setup__` but you can force it via
        `dj_xmlid_module` context var.
        """
        return self.env.context.get('dj_xmlid_module') or '__setup__'

    @tools.ormcache('self', 'key')
    def _dj_global_config(self, key=None):
        """Retrieve default global config for xmlid fields."""
        config = self.env['dj.equalizer'].search([
            ('model', '=', self._name),
        ], limit=1)
        return config.get_conf(key)

    def _dj_xmlid_export_name(self):
        """Customize xmlid name for dj compilation.

        You can specify field names by model name
        into context variable `dj_xmlid_fields_map`
        to be used for xmlid generation.
        Strings will be normalized.
        """
        name = [self._table, str(self.id)]  # std odoo default
        mapping = self.env.context.get('dj_xmlid_fields_map') or {}
        global_config = self._dj_global_config()
        xmlid_fields = (mapping.get(self._name, []) or
                        global_config.get('xmlid_fields', []))
        if not xmlid_fields and 'name' in self:
            # No specific configuration: we assume we can use name as default
            xmlid_fields.append('name')
        if xmlid_fields:
            name = [self._table, ]
            if global_config.get('xmlid_table_name'):
                name = [global_config['xmlid_table_name'], ]
            xmlid_fields_name = []
            for key in xmlid_fields:
                if not self[key]:
                    continue
                value = to_str(self[key], safe=True)
                if isinstance(value, str):
                    value = slugify(value).replace('-', '_')
                elif isinstance(value, models.BaseModel):
                    value = slugify(value.display_name).replace('-', '_')
                elif isinstance(value, (int, float)):
                    value = str(value)
                xmlid_fields_name.append(value)
            if global_config.get('xmlid_policy') == 'hash':
                # sometime this is the only way to get unique xmlids
                # (ir.default for instance).
                name.append(self._hash_them(tuple(xmlid_fields_name)))
            else:
                name.extend(xmlid_fields_name)
        if (self.env.context.get('dj_multicompany') and
                'company_id' in self and self.company_id.aka):
            # discriminate by company `aka` code
            name.insert(0, self.company_id.normalized_aka())
        return '_'.join(name)

    def _dj_export_xmlid(self):
        """Shortcut to force dj xmlid generation."""
        return self.with_context(dj_export=1)._BaseModel__export_xml_id()

    def _BaseModel__export_xml_id(self):
        """Customize xmlid creation.

        Barely copied from `odoo.models` and hacked a bit.

        Being a private method we are forced to name it like this.
        See https://docs.python.org/2/tutorial/classes.html#private-variables-and-class-local-references
        """  # noqa
        if not self.env.context.get('dj_export'):
            return super(Base, self)._BaseModel__export_xml_id()

        module = self._dj_xmlid_export_module()
        base_name = self._dj_xmlid_export_name()

        if not self._is_an_ordinary_table():
            raise Exception(
                "You can not export the column ID of model %s, because the "
                "table %s is not an ordinary table."
                % (self._name, self._table))
        ir_model_data = self.sudo().env['ir.model.data']

        # we want to discard autogenerated xmlids
        # and keep only modules' ones
        data = ir_model_data.search([
            ('model', '=', self._name),
            ('res_id', '=', self.id),
            ('module', 'not in', ('__export__', module)),
        ], order='create_date desc', limit=1)
        if data and not self.env.context.get('dj_xmlid_force'):
            if data.module:
                return '%s.%s' % (data.module, data.name)
            else:
                return data.name
        else:
            name = base_name[:]

            # same name, same record
            existing = ir_model_data.search([
                ('module', '=', module),
                ('name', '=', name),
                ('model', '=', self._name),
                ('res_id', '=', self.id),
            ], limit=1)
            if existing:
                # cool, use it
                return module + '.' + name

            # in case of collision, generate a new one
            postfix = 0
            while ir_model_data.search([('module', '=', module),
                                        ('name', '=', name)], limit=1):
                postfix += 1
                name = '%s_%d' % (base_name, postfix)
            if not self.env.context.get('dj_xmlid_skip_create'):
                ir_model_data.create({
                    'model': self._name,
                    'res_id': self.id,
                    'module': module,
                    'name': name,
                })
            return to_str(module + '.' + name)

    @api.multi
    def read(self, fields=None, load='_classic_read'):
        """Handle special fields value for dj export."""
        res = super(Base, self).read(fields=fields, load=load)
        if (not self.env.context.get('dj_export') or
                self.env.context.get('dj_skip_file_handling')):
            return res
        self._dj_handle_special_fields_read(res, _fields=fields)
        return res

    def _dj_handle_special_fields_read(self, records, _fields=None):
        if self.env.context.get('dj_read_skip_special_fields'):
            return
        if not records:
            return
        if _fields is None:
            _fields = list(records[0].keys())
        for fname, info in self._dj_special_fields(_fields):
            self._dj_handle_file_field_read(fname, info, records)

    # you can customized this per-model
    _dj_file_fields_types = ('html', 'binary', )
    _dj_file_fields_names = ('arch_db', )
    _dj_path_prefix = 'dj_path:'

    def _dj_special_fields(self, _fields=None):
        res = []
        fields_info = self.fields_get(_fields)
        for fname, info in fields_info.items():
            if self._dj_is_file_field(fname, info):
                res.append((fname, info))
        return res

    def _dj_is_file_field(self, fname, info):
        return (info['type'] in self._dj_file_fields_types or
                fname in self._dj_file_fields_names)

    def _dj_handle_file_field_read(self, fname, info, records):
        for rec in records:
            ob = self.browse(rec['id'])
            self.invalidate_cache([fname])
            if rec[fname]:
                rec[fname] = self._dj_file_to_path(ob, fname, info)

    def _dj_file_to_path(self, rec, fname, info=None):
        info = info or self.fields_get([fname])[fname]
        xmlid = rec._dj_export_xmlid()
        # TODO: handle path from song settings
        path = '{prefix}data/binaries/{xmlid}__{fname}'
        export_lang = self.env.context.get('dj_export_lang', '')
        if export_lang:
            path += '_{lang}'
        path += '.{ext}'
        ext, _ = self._dj_guess_filetype(fname, rec, info=info)
        res = path.format(
            prefix=self._dj_path_prefix,
            xmlid=xmlid, fname=fname,
            lang=export_lang, ext=ext)
        if fname == 'arch_db':
            return '<odoo><path>' + res + '</path></odoo>'
        return res

    def _dj_guess_filetype(self, fname, record, info=None):
        record = record.with_context(dj_skip_file_handling=True)
        content = record[fname]
        if fname == 'arch_db':
            return 'xml', content
        info = info or self.fields_get([fname])[fname]
        if info['type'] == 'html':
            return 'html', content
        # guess filename from mimetype
        if is_xml(content):
            return 'xml', content
        if info['type'] == 'binary':
            content = decode64(content)
        elif info['type'] == 'text':
            content = encode64(content.encode('utf-8'))
        mime = tools.mimetypes.guess_mimetype(content)
        if mime:
            if mime == 'text/plain':
                # TODO: any better option?
                # `guess_extension` works very randomly here.
                # Let's stick to txt for now.
                ext = 'txt'
            else:
                # remove dot
                ext = mimetypes.guess_extension(mime)
                if ext:
                    ext = ext[1:]
                else:
                    # lookup for a default fallback
                    ext = self._dj_default_mimetype_ext_mapping.get(
                        mime, 'unknown')
            return ext, content
        return 'unknown', content

    _dj_default_mimetype_ext_mapping = {
        'image/x-icon': 'ico'
    }

    def _dj_file_content_to_fs(self, fname, record, info=None):
        """Convert values to file system value.

        Called by `_handle_special_fields` when song's data is prepared.
        """
        _, content = self._dj_guess_filetype(fname, record)
        return content

    @api.multi
    def write(self, vals):
        self._dj_handle_special_fields_write(vals)
        return super(Base, self).write(vals)

    def _dj_handle_special_fields_write(self, vals):
        if not vals:
            return
        for fname, info in self._dj_special_fields(list(vals.keys())):
            if vals[fname]:
                self._dj_handle_file_field_write(fname, info, vals)

    def _dj_handle_file_field_write(self, fname, info, vals):
        self.invalidate_cache([fname])
        vals[fname] = self._dj_path_to_file(fname, info, vals[fname])

    def _dj_path_to_file(self, fname, info, path):
        # special case: xml validation is done for fields like `arch_db`
        # so we need to wrap/unwrap w/ <odoo/> tag
        if not is_string(path):
            return path
        path = to_str(path)
        path = path.replace('<odoo><path>', '').replace('</path></odoo>', '')
        if not path.startswith(self._dj_path_prefix):
            return path
        path = path[len(self._dj_path_prefix):]
        base_path = '/opt/odoo'  # TODO: compute this
        abs_path = os.path.join(base_path, path)
        read_mode = 'r'
        if info['type'] == 'binary':
            read_mode = 'rb'
        with open(abs_path, read_mode) as ff:
            content = ff.read()
            if info['type'] == 'binary':
                content = encode64(content)
            return content

    @api.model
    def create(self, vals):
        self._dj_handle_special_fields_write(vals)
        return super(Base, self).create(vals)
