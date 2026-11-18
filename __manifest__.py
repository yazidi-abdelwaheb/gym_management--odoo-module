
{
    'name': 'Gym Management',
    'summary': 'Gym member management with automatic portal accounts',
    'description': """
        Manage gym members, their contact details, registration dates,
        profile pictures, and linked Odoo portal accounts with email invitations.
    """,

    'author': 'Abdelwaheb Yazidi',
    'website': 'https://github.com/yazidi-abdelwaheb',

    'category': 'Services',
    'version': '20.0.1.0.0',

    'depends': [
        'base',
        'portal',
    ],

    'data': [
        'security/groups.xml',
        'security/ir.access.csv',
        'views/gym_member_views.xml',
        'views/gym_menus.xml',
        'views/templates.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'gym_management/static/src/js/gym_dashboard.js',
            'gym_management/static/src/xml/gym_dashboard.xml',
            'gym_management/static/src/scss/gym_dashboard.scss',
        ],
    },

    'demo': [
        'demo/demo.xml',
    ],

    'application': True,
    'installable': True,
}
