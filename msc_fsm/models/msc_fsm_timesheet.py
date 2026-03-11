# Copyright 2025 Xtendoo Software SLU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MscFsmTimesheet(models.Model):
    _name = "msc.fsm.timesheet"
    _description = "Parte de Horas en Orden de Trabajo"

    order_id = fields.Many2one(
        "msc.fsm.order",
        string="Orden de Trabajo",
        required=True,
        ondelete="cascade",
        index=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Empleado",
        required=True,
        default=lambda self: self.env.user.employee_id,
    )
    date = fields.Date(string="Fecha", required=True, default=fields.Date.context_today)
    name = fields.Char(string="Descripción", required=True)
    duration = fields.Float(string="Horas", required=True, default=0.0)

