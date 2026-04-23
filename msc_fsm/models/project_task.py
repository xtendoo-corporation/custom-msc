# Copyright 2025 Xtendoo Software SLU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import api, fields, models, _


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # Integración con FSM
    fsm_order_id = fields.Many2one(
        'msc.fsm.order',
        string='Orden de Servicio FSM',
        help="Orden de servicio de campo relacionada"
    )
    is_fsm_task = fields.Boolean(
        string='Es Tarea FSM',
        compute='_compute_is_fsm_task',
        store=True
    )

    @api.depends('project_id.is_fsm')
    def _compute_is_fsm_task(self):
        for task in self:
            task.is_fsm_task = bool(task.project_id and task.project_id.is_fsm)

    def action_view_fsm_order(self):
        """Ver la orden FSM relacionada"""
        if self.fsm_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'msc.fsm.order',
                'res_id': self.fsm_order_id.id,
                'view_mode': 'form',
            }


class ProjectProject(models.Model):
    _inherit = 'project.project'

    is_fsm = fields.Boolean(
        string='Proyecto FSM',
        help="Este proyecto se usa para gestión de servicios de campo"
    )
