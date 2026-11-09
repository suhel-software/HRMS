{
    'name': 'DSL HRMS - Fixed Asset Management Suite',
    'version': '18.0.2.0.0',
    'category': 'Accounting/Accounting',
    'sequence': 11,
    'summary': 'Complete Fixed Asset module: depreciation engine, asset register, QR tags, custody, transfer, '
               'maintenance, warranty & insurance, physical verification, disposal, depreciation schedule and dashboard',
    'description': """
DSL Enterprise Fixed Asset Management Suite (Odoo 18)
=====================================================

Self-contained Fixed Asset module. The complete asset & depreciation engine
(account.asset, account.asset.group, asset.modify wizard, depreciation schedule report,
auto-asset creation from vendor bills) lives in this module and only depends on
DSL_HRMS_accounting for the accounting / reporting framework.

* Depreciation engine: straight line, declining, declining-then-linear, prorata, pause / resume,
  gross increase, re-evaluation, sell / dispose with gain / loss posting
* Auto-create assets from vendor bills per account, asset models and asset groups
* Depreciation Schedule financial report
* Asset Dashboard with live KPIs, trend chart and breakdowns
* Asset register with auto asset code, barcode, serial / model number, brand and photo
* QR-coded asset tags, asset card, asset register and handover reports
* Hierarchical locations, employee custody, approval-based transfers
* Preventive / corrective maintenance with recurrence, cost and vendor bill
* Warranty and insurance tracking with reminders
* Physical verification (asset audit)
""",
    'author': 'DSL Enterprise HRMS',
    'depends': [
        'mail',
        'account',
        'analytic',
        'hr',
        'DSL_HRMS_core',
        'DSL_HRMS_accounting',
        'DSL_HRMS_account_reports',
    ],
    'data': [
        # security
        'security/security.xml',
        'security/ir.model.access.csv',
        # depreciation engine
        'views/asset_modify_views.xml',
        'views/asset_engine_views.xml',
        'views/asset_group_views.xml',
        'views/account_move_asset_views.xml',
        'data/depreciation_report.xml',
        # asset management layer
        'data/sequence_data.xml',
        'data/location_data.xml',
        'data/cron_data.xml',
        'report/asset_reports.xml',
        'views/asset_location_views.xml',
        'views/asset_assignment_views.xml',
        'views/asset_transfer_views.xml',
        'views/asset_maintenance_views.xml',
        'views/asset_verification_views.xml',
        'views/account_asset_views.xml',
        'views/dashboard_views.xml',
        'views/menus.xml',
        'data/post_install_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'DSL_HRMS_fixed_asset/static/src/components/**/*',
            'DSL_HRMS_fixed_asset/static/src/scss/account_asset.scss',
            'DSL_HRMS_fixed_asset/static/src/scss/fixed_asset.scss',
            'DSL_HRMS_fixed_asset/static/src/dashboard/asset_dashboard.js',
            'DSL_HRMS_fixed_asset/static/src/dashboard/asset_dashboard.xml',
        ],
        'web.assets_web_dark': [
            'DSL_HRMS_fixed_asset/static/src/scss/account_asset.dark.scss',
        ],
        'DSL_HRMS_account_reports.assets_pdf_export': [
            'DSL_HRMS_fixed_asset/static/src/scss/account_asset.scss',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
