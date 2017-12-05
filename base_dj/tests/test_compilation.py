# -*- coding: utf-8 -*-
# Copyright 2017 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

from . common import BaseCompilationCase


class CompilationCase(BaseCompilationCase):

    def test_disc_path(self):
        genre = self.env.ref('base_dj.test_genre')
        comp = self.env['dj.compilation'].create({
            'name': 'Foo',
            'genre_id': genre.id,
        })
        # name is normalized
        self.assertEqual(comp.name, 'foo')
        # path defaults to songs/{data_mode}/generated/{genre}_{name}.py
        self.assertEqual(
            comp.disc_full_path(),
            'songs/install/generated/dj_test_foo.py'
        )

    def test_disc_path_custom(self):
        genre = self.env.ref('base_dj.test_genre')
        comp = self.env['dj.compilation'].create({
            'name': 'Bar Baz',
            'genre_id': genre.id,
            'disc_path': 'songs/{name}.py',
        })
        # name is normalized
        self.assertEqual(comp.name, 'bar_baz')
        # path defaults to songs/{data_mode}/generated/{genre}_{name}.py
        self.assertEqual(
            comp.disc_full_path(),
            'songs/bar_baz.py'
        )

    def test_burn_and_test1(self):
        fixture = 'fixture_comp1'
        expected_path = 'songs/install/generated/dj_test_comp1.py'
        self._burn_and_test(fixture, expected_path, 'base_dj.test_comp1')

    def test_burn_defer_parent(self):
        fixture = 'fixture_defer_parent'
        expected_path = 'songs/install/generated/dj_test_comp4.py'
        self._burn_and_test(fixture, expected_path, 'base_dj.test_comp4')

    def test_burn_contents(self):
        fixture = 'fixture_comp1'
        self._load_xml('base_dj', 'tests/fixtures/%s.xml' % fixture)
        comp = self.env.ref('base_dj.test_comp1')
        tracks = comp.with_context(
            dj_read_skip_special_fields=True).get_all_tracks()
        paths = sorted([x[0] for x in tracks])
        expected = [
            'DEV_README.rst',
            'data/install/generated/dj_test/res.company.csv',
            'data/install/generated/dj_test/res.partner.csv',
            'data/install/generated/dj_test/res.users.csv',
            'songs/install/generated/__init__.py',
            'songs/install/generated/dj_test_comp1.py'
        ]
        self.assertListEqual(paths, expected)

    def test_burn_contents_with_core(self):
        fixture = 'fixture_comp1'
        self._load_xml('base_dj', 'tests/fixtures/%s.xml' % fixture)
        fixture = 'fixture_comp_core'
        self._load_xml('base_dj', 'tests/fixtures/%s.xml' % fixture)
        comp = self.env.ref('base_dj.test_comp1')
        tracks = comp.with_context(
            dj_read_skip_special_fields=True).get_all_tracks()
        paths = sorted([x[0] for x in tracks])
        expected = [
            'DEV_README.rst',
            'data/install/generated/dj_test/ir.default.csv',
            'data/install/generated/dj_test/res.company.csv',
            'data/install/generated/dj_test/res.lang.csv',
            'data/install/generated/dj_test/res.partner.csv',
            'data/install/generated/dj_test/res.users.csv',
            'songs/install/generated/__init__.py',
            'songs/install/generated/dj_test_comp1.py',
            'songs/install/generated/dj_test_core1.py',
        ]
        self.assertListEqual(paths, expected)
