# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models, fields
from urllib.parse import urlencode


class BurnWiz(models.TransientModel):
    _name = 'dj.compilation.burn.wiz'

    compilation_id = fields.Many2one(
        string='Compilation to burn',
        comodel_name='dj.compilation',
        required=True,
        readonly=True,
        default=lambda self: self.env.context.get('active_id'),
    )
    dj_force_data_mode = fields.Selection(
        string='Burn mode',
        help='Force data mode only for this burn session. '
             'When this diverges from compilation data mode '
             '`Force XIDs` is activated but '
             'newly generated XIDs will not be stored.',
        required=True,
        selection=[
            ('install', 'Install'),
            ('sample', 'Sample'),
        ],
    )
    core_compilation_ids = fields.Many2many(
        string='Core compilations',
        comodel_name='dj.compilation',
        help='Force included core compilations for this burn session.',
        readonly=True,
    )
    dj_exclude_core = fields.Boolean(
        string='Exclude core compilations',
        help='Force EXCLUDE core compilations for this burn session. '
             'Only current compilation will be burnt.',
    )
    dj_xmlid_force = fields.Boolean(
        string='Force XIDs',
        help='Force XIDs (re)generation. '
             'When this option is on XIDs are re-generated for all records '
             'that are not module specific (like "base.main_company"). '
             'Combined with "Skip creation of new XIDs" you can generate '
             'one-shot XIDs that are not stored in DB. '
             'You could use this to fix some bad XIDs or '
             'replace outdated XIDs due to XID policy updates.'
    )
    dj_xmlid_skip_create = fields.Boolean(
        string='Skip creation of new XIDs',
        help='Do not store newly generated XIDs',
        default=False,
    )
    burn_url = fields.Char(
        string='Share burn URL',
        default='',
        readonly=True,
    )

    @api.onchange('compilation_id')
    def _onchange_compilation_id(self):
        self.update({
            'dj_force_data_mode': self.compilation_id.data_mode,
            'core_compilation_ids': self.compilation_id.core_compilation_ids,
        })
        self._update_url()

    @api.onchange('dj_force_data_mode')
    def _onchange_data_mode(self):
        if self.dj_force_data_mode != self.compilation_id.data_mode:
            self.update({
                'dj_xmlid_force': True,
                'dj_xmlid_skip_create': True,
            })
        else:
            self.update({
                'dj_xmlid_force': False,
                'dj_xmlid_skip_create': False,
            })
        self._update_url()

    @api.onchange('dj_exclude_core')
    def _onchange_dj_exclude_core(self):
        core_comps = self.compilation_id.core_compilation_ids
        if self.dj_exclude_core:
            core_comps = False
        self.update({
            'core_compilation_ids': core_comps,
        })
        self._update_url()

    def _update_url(self):
        config = {}
        for fname in self.compilation_id.dj_burn_options_flags:
            if self[fname]:
                config[fname] = self[fname]
        self.burn_url = '/dj/download/compilation/{id}?{config}'.format(
            id=self.compilation_id.id,
            config=urlencode(config)
        )

    @api.multi
    def action_burn(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'target': 'new',
            'url': self.burn_url,
        }
