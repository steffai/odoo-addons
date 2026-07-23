==========================
Automation Workflow Bareos
==========================

Creates **To-Do activities** automatically when an incoming email (or
customer message) arrives on a record, so the responsible user is
reminded to react.

Supported models
================

The module ships with automated rules for the following models:

+------------------+--------------------+---------------+
| Model            | Responsible field  | Cardinality   |
+==================+====================+===============+
| ``crm.lead``     | ``user_id``        | single user   |
+------------------+--------------------+---------------+
| ``sale.order``   | ``user_id``        | single user   |
+------------------+--------------------+---------------+
| ``purchase.order``| ``user_id``       | single user   |
+------------------+--------------------+---------------+
| ``account.move`` | ``invoice_user_id``| single user   |
+------------------+--------------------+---------------+
| ``project.task`` | ``user_ids``       | first of M2M  |
+------------------+--------------------+---------------+

How it works
============

The module uses Odoo 19's built-in ``base_automation`` ("Automated Actions")
with the ``on_message_received`` trigger. Odoo classifies a message as
"incoming" when the author is an external / portal partner
(``partner_share = True``) or has no known author --- i.e. a real customer
replying by email. Internal users posting in the chatter are classified
as ``on_message_sent`` and do **not** trigger an activity.

The activity created is a To-Do with:

- **Summary**: ``react to message``
- **Deadline**: today
- **Note**: ``<date>: created``

Deduplication
-------------

If a ``react to message`` To-Do already exists on the record, it is
**updated** (deadline bumped to today, ``<date>: updated`` appended to the
note) instead of creating a duplicate. At most one such activity per record.

Customizing the rules
=====================

The automation data is installed with ``noupdate="1"``. This means the
rules are created once on install and **not overwritten on module
upgrade** --- so you can tweak them in the UI without losing your changes
when the module is updated.

To change a rule:

1. Activate **developer mode** (Settings → scroll to bottom →
   *Activate the developer mode*).
2. Go to **Settings → Technical → Automated Actions**.
3. Find the rule named *Incoming Message Activity (...)* for the model
   you want to adjust.
4. You can:

   - **Disable** a rule by unchecking *Active*.
   - **Edit the action**: open the server action and change the *Python Code*.
5. Save. The change takes effect immediately for new incoming messages.

What you typically want to tweak:

The server action calls ``_schedule_incoming_message_activity`` with these
customizable keyword arguments (all have sensible defaults):

- **``summary``** — activity summary text (default ``"react to message"``)
- **``activity_type_xmlid``** — XML ID of the activity type
  (default ``"mail.mail_activity_data_todo"``)
- **``user_field``** — relational field holding the responsible user(s)
  (default ``"user_id"``)

For example, to use a different activity type::

    record._schedule_incoming_message_activity(
        user_field="user_id",
        activity_type_xmlid="my_module.my_activity_type",
        summary="Please follow up",
    )
- **Only specific records** --- set a *Filter Domain* on the automation,
  e.g. ``[("stage_id", "=", ref("psc_stage_lead"))]`` to fire only on
  leads in a given stage

Propagating code changes
========================

If you change the data XML in this module and want those changes to
overwrite the existing database records, you need to lift the
``noupdate`` flag for the affected records. Two options:

Option A: one-off, via Odoo shell / server action
--------------------------------------------------

::

    # Set noupdate=False on the ir.model.data entry so the upgrade
    # overwrites the existing database record.
    env['ir.model.data'].search([
        ('module', '=', 'automation_workflow_bareos'),
        ('name', '=', 'automation_incoming_activity_crm_lead'),
    ]).write({'noupdate': False})
    # Then run: odoo --update=automation_workflow_bareos --stop-after-init

Option B: migration script
--------------------------

Add a ``migrations/<new_version>/post-migrate.py``::

    def migrate(cr, version):
        # Allow the upgrade to overwrite the affected records
        cr.execute("""
            UPDATE ir_model_data
            SET noupdate = false
            WHERE module = 'automation_workflow_bareos'
              AND name IN (
                'automation_incoming_activity_crm_lead',
                'action_incoming_activity_crm_lead'
              )
        """)

Bump the module version in ``__manifest__.py`` and run
``odoo --update=automation_workflow_bareos``.  The ``--update`` flag only
picks up changes when the version string has actually changed.

Adding a new model
==================

Add a ``<record>`` block for both ``base.automation`` and ``ir.actions.server``
to ``data/base_automation_data.xml``, following the existing pattern.
New records (not previously installed) are created on the next
``--update`` regardless of ``noupdate``, so no migration is needed for
additions --- only for modifications of existing records.

License
=======

LGPL-3
