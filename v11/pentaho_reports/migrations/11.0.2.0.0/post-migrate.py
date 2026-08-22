# -*- coding: utf-8 -*-


def migrate(cr, version):
    """The external Pentaho server integration is gone: drop its parameters.

    pentaho.rendering.mode and pentaho.native.fallback were created without
    XML IDs, so the regular orphaned-data cleanup never removes them.
    """
    cr.execute("""
        DELETE FROM ir_config_parameter
              WHERE key IN ('pentaho.server.url',
                            'pentaho.odoo.xml.interface',
                            'pentaho.odoo.xml.port',
                            'pentaho.postgres.host',
                            'pentaho.postgres.port',
                            'pentaho.postgres.login',
                            'pentaho.postgres.password',
                            'pentaho.rendering.mode',
                            'pentaho.native.fallback')
    """)
