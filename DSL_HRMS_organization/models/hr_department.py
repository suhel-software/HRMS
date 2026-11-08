# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HrDepartmentOrg(models.Model):
    _inherit = 'hr.department'

    code = fields.Char(string='Department Code', index=True)
    division_id = fields.Many2one(
        'dsl.hr.division',
        string='Division / Wing',
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    cost_center_id = fields.Many2one(
        'dsl.cost.center',
        string='Cost Center',
        domain="[('company_id', '=', company_id)]",
    )
    department_type = fields.Selection(
        selection=[
            ('division', 'Corporate Division'),
            ('department', 'Department'),
            ('section', 'Section'),
            ('unit', 'Unit / Team'),
            ('line', 'Production Floor / Line'),
        ],
        string='Unit Type',
        default='department',
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    budget_amount = fields.Monetary(
        string='Annual Payroll Budget',
        currency_field='currency_id',
    )
    manpower_budget = fields.Integer(
        string='Sanctioned Headcount',
        default=10,
        help='Approved maximum headcount for this department/section',
    )
    vacancy_count = fields.Integer(
        string='Open Vacancies',
        compute='_compute_vacancy_count',
    )

    @api.depends('manpower_budget', 'total_employee')
    def _compute_vacancy_count(self):
        for dept in self:
            dept.vacancy_count = max((dept.manpower_budget or 0) - (dept.total_employee or 0), 0)

    @api.model
    def get_organization_chart_data(self, company_id=False):
        """Return both Department Organogram and Employee Reporting Organogram trees
        strictly scoped to the current user's allowed companies AND allowed branches."""
        user = self.env.user.sudo()
        allowed_ids = user.company_ids.ids
        allowed_branch_ids = user._get_effective_branch_ids() if hasattr(user, '_get_effective_branch_ids') else []
        strict_branch = user._has_strict_branch_lock() if hasattr(user, '_has_strict_branch_lock') else False

        if company_id and int(company_id) in allowed_ids:
            comp_filter = [('company_id', '=', int(company_id))]
        elif company_id and int(company_id) not in allowed_ids:
            comp_filter = [('id', '=', 0)]
        else:
            comp_filter = ['|', ('company_id', '=', False), ('company_id', 'in', allowed_ids)]

        if strict_branch:
            dept_emp_filter = comp_filter + [('branch_id', 'in', allowed_branch_ids)]
            job_filter = comp_filter + ['|', ('branch_id', '=', False), ('branch_id', 'in', allowed_branch_ids)]
        else:
            dept_emp_filter = comp_filter
            job_filter = comp_filter

        companies = self.env['res.company'].sudo().search_read(
            [('id', 'in', allowed_ids)], ['id', 'name'], order='sequence, id'
        )
        depts = self.sudo().search(dept_emp_filter, order='name')
        emps = self.env['hr.employee'].sudo().search(dept_emp_filter, order='name')
        has_branch = 'dsl.branch' in self.env

        type_labels = dict(self._fields['department_type'].selection)

        # 1. Build Department Tree
        dept_map = {}
        for d in depts:
            dept_map[d.id] = {
                'id': d.id,
                'name': d.name,
                'code': d.code or f'D-{d.id:02d}',
                'unit_type': type_labels.get(d.department_type or 'department', 'Department'),
                'parent_id': d.parent_id.id or False,
                'company_name': d.company_id.name or 'All Companies',
                'division_name': d.division_id.name or '',
                'branch_name': d.branch_id.name if has_branch and getattr(d, 'branch_id', False) else '',
                'manager_id': d.manager_id.id or False,
                'manager_name': d.manager_id.name or 'Unassigned',
                'manager_job': d.manager_id.job_title or (d.manager_id.job_id.name if d.manager_id.job_id else ''),
                'employee_count': d.total_employee or 0,
                'manpower_budget': d.manpower_budget or 0,
                'vacancy_count': d.vacancy_count or 0,
                'children': [],
            }

        dept_roots = []
        for did, dnode in dept_map.items():
            pid = dnode['parent_id']
            if pid and pid in dept_map:
                dept_map[pid]['children'].append(dnode)
            else:
                dept_roots.append(dnode)

        # 2. Build Employee Reporting Tree
        emp_map = {}
        for e in emps:
            emp_map[e.id] = {
                'id': e.id,
                'name': e.name,
                'job_title': e.job_title or (e.job_id.name if e.job_id else 'Team Member'),
                'department_name': e.department_id.name or 'General',
                'company_name': e.company_id.name or '',
                'grade_name': e.grade_id.code if getattr(e, 'grade_id', False) else '',
                'branch_name': e.branch_id.name if has_branch and getattr(e, 'branch_id', False) else '',
                'parent_id': e.parent_id.id or False,
                'work_email': e.work_email or '',
                'children': [],
            }

        emp_roots = []
        for eid, enode in emp_map.items():
            pid = enode['parent_id']
            if pid and pid in emp_map and pid != eid:
                emp_map[pid]['children'].append(enode)
            else:
                emp_roots.append(enode)

        return {
            'companies': companies,
            'dept_roots': dept_roots,
            'emp_roots': emp_roots,
            'stats': {
                'total_departments': len(dept_map),
                'total_employees': len(emp_map),
                'total_designations': self.env['hr.job'].sudo().search_count(job_filter),
                'total_grades': self.env['dsl.hr.grade'].sudo().search_count(
                    ['|', ('company_id', '=', False), ('company_id', 'in', allowed_ids)]
                ),
                'open_vacancies': sum(n['vacancy_count'] for n in dept_map.values()),
            },
        }

