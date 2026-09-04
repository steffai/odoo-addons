=================================
Partner Domain Collect
=================================

Assigns contacts to companies based on email domains.

Contacts are often created by Odoo (e.g. from an incoming email) without
being linked to a company. This module helps to assign them to the right
company.

Features
========

* A company can collect email domains (``domain_collect_ids_bareos``) on
  the "Domains" tab of the company form.

* On the company form, a *Potential Contacts* box shows how many unassigned
  contacts match one of the collected domains. Clicking it opens a wizard
  listing those contacts, where they can be selected and assigned to the
  company.

* If a company has no collected domains, the domain of its website URL is
  used instead.

* On a contact without a parent company, the form suggests companies whose
  collected (or website) domain matches the contact's email address. A
  contact can be added to a suggested company with one click. Contacts that
  only have a *Company Name* set (but no parent) are covered as well.

Usage
=====

1. Open the company (a contact with *Company* checked).
2. On the *Domains* tab, add email domains (e.g. ``bareos.com``).
3. The *Potential Contacts* box shows matching contacts. Click it, select
   the contacts and press *Assign*.

Or, when editing a contact that has no company yet, use the *Suggested companies*
section to add it to a matching company.
