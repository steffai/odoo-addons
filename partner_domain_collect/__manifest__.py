{
    "name": "Partner Domain Collect",
    "version": "19.0.1.0.0",
    "summary": "Assign contacts to companies based on email domains",
    "author": "Bareos GmbH & Co. KG",
    "license": "LGPL-3",
    "category": "Contacts",
    "depends": ["contacts"],
    "data": [
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
