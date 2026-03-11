# Copyright 2025 Xtendoo Software SLU
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from datetime import datetime, timedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class DaruclimeFSMOrder(models.Model):
    _name = "msc.fsm.order"
    _description = "Orden de Trabajo"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "priority_level desc, date_scheduled asc, id desc"
    _rec_name = "name"

    # Campos básicos
    name = fields.Char(
        string="Número",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("Nuevo"),
        tracking=True,
    )

    # Información del cliente y ubicación
    partner_id = fields.Many2one(
        "res.partner",
        string="Cliente",
        required=True,
        tracking=True,
        help="Cliente para quien se realiza el servicio",
    )
    location_id = fields.Many2one(
        "res.partner",
        string="Dirección del Servicio",
        tracking=True,
        domain="[('parent_id', '=', partner_id)]",
        help="Dirección de entrega donde se realizará el servicio",
    )
    contact_id = fields.Many2one(
        "res.partner",
        string="Contacto",
        help="Persona o empresa de contacto en la ubicación del servicio",
    )

    # Información del servicio
    description = fields.Text(
        string="Descripción del Trabajo", required=True, tracking=True
    )
    internal_note = fields.Text(
        string="Notas Internas", help="Notas internas no visibles para el cliente"
    )
    customer_note = fields.Text(
        string="Notas del Cliente", help="Notas visibles para el cliente"
    )

    # Gestión de estados y prioridades
    stage_id = fields.Many2one(
        "msc.fsm.stage",
        string="Etapa",
        required=True,
        tracking=True,
        group_expand="_read_group_stage_ids",
        default=lambda self: self._get_default_stage(),
    )
    priority_level = fields.Selection(
        selection=[
            ("0", "Muy Baja"),
            ("1", "Baja"),
            ("2", "Normal"),
            ("3", "Alta"),
            ("4", "Muy Alta"),
            ("5", "Urgente"),
        ],
        string="Prioridad",
        default="2",
        tracking=True,
    )

    color = fields.Char(string="Color", related="stage_id.color", store=True)
    is_closed = fields.Boolean(
        string="Cerrado", related="stage_id.is_closed", store=True
    )

    # Fechas y tiempo
    date_created = fields.Datetime(
        string="Fecha de Creación", default=fields.Datetime.now, readonly=True
    )
    date_scheduled = fields.Datetime(
        string="Fecha Programada",
        tracking=True,
        help="Fecha y hora programada para el servicio",
    )
    date_start = fields.Datetime(string="Fecha de Inicio", tracking=True)
    date_end = fields.Datetime(string="Fecha de Finalización", tracking=True)
    duration = fields.Float(
        string="Duración (Horas)",
        compute="_compute_duration",
        store=True,
        help="Duración del trabajo en horas",
    )

    # Técnicos (eliminamos la referencia al equipo inexistente)
    person_ids = fields.Many2many(
        "hr.employee",
        "msc_fsm_order_employee_rel",
        "order_id",
        "employee_id",
        string="Técnicos Asignados",
        tracking=True,
        help="Empleados asignados a esta orden de trabajo",
    )

    # Equipos y servicios
    tag_ids = fields.Many2many(
        "msc.fsm.tag",
        string="Etiquetas",
        help="Etiquetas para clasificar y analizar órdenes",
    )

    # Materiales y Horas
    material_line_ids = fields.One2many(
        "msc.fsm.material", "order_id", string="Materiales"
    )
    timesheet_line_ids = fields.One2many(
        "msc.fsm.timesheet", "order_id", string="Partes de Horas"
    )

    # Integración con órdenes de venta
    sale_order_ids = fields.One2many(
        "sale.order",
        "fsm_order_id",
        string="Órdenes de Venta",
        help="Órdenes de venta relacionadas con esta orden de trabajo",
    )
    sale_count = fields.Integer(
        string="Número de Órdenes de Venta", compute="_compute_sale_count"
    )

    # Portal
    access_url = fields.Char(string="URL de Acceso", compute="_compute_access_url")
    company_id = fields.Many2one(
        "res.company",
        string="Compañía",
        required=True,
        default=lambda self: self.env.company,
        help="Compañía para la que se realiza esta orden de trabajo",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("Nuevo")) == _("Nuevo"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "msc.fsm.order"
                ) or _("Nuevo")
            # Garantizar etapa por defecto si no viene informada
            if not vals.get("stage_id"):
                vals["stage_id"] = self._get_default_stage()
        records = super().create(vals_list)
        # Notificar a técnicos asignados en la creación
        for record in records:
            if record.person_ids:
                record._notify_assigned_technicians(record.person_ids)
        return records

    def write(self, vals):
        # Capturar técnicos anteriores antes del write
        if "person_ids" in vals:
            old_persons = {rec.id: rec.person_ids for rec in self}
        res = super().write(vals)
        # Detectar nuevos técnicos y notificarles
        if "person_ids" in vals:
            for rec in self:
                new_persons = rec.person_ids - old_persons.get(
                    rec.id, self.env["hr.employee"]
                )
                if new_persons:
                    rec._notify_assigned_technicians(new_persons)
        return res

    def _notify_assigned_technicians(self, employees):
        """Envía email de notificación a los técnicos recién asignados."""
        for employee in employees:
            # Obtener email: del usuario vinculado o del work_email del empleado
            email = False
            if employee.user_id and employee.user_id.email:
                email = employee.user_id.email
            elif employee.work_email:
                email = employee.work_email
            if not email:
                continue

            priority_map = dict(self._fields["priority_level"].selection)
            priority_label = priority_map.get(self.priority_level, "")
            location_text = (
                self.location_id.contact_address
                if self.location_id
                else "No especificada"
            )
            body_html = _(
                '<div style="margin:0;padding:0;font-family:Arial,sans-serif;">'
                "<p>Hola <strong>%(tech_name)s</strong>,</p>"
                "<p>Se te ha asignado una nueva orden de trabajo. A continuación los detalles:</p>"
                '<table border="1" cellpadding="8" style="border-collapse:collapse;width:100%%;margin:10px 0;">'
                '<tr style="background-color:#f2f2f2;">'
                '<td style="width:30%%"><strong>Número de Orden:</strong></td>'
                "<td>%(order_name)s</td></tr>"
                "<tr><td><strong>Cliente:</strong></td>"
                "<td>%(partner_name)s</td></tr>"
                '<tr style="background-color:#f2f2f2;">'
                "<td><strong>Descripción:</strong></td>"
                "<td>%(description)s</td></tr>"
                "<tr><td><strong>Fecha Programada:</strong></td>"
                "<td>%(date_scheduled)s</td></tr>"
                '<tr style="background-color:#f2f2f2;">'
                "<td><strong>Prioridad:</strong></td>"
                "<td>%(priority)s</td></tr>"
                "<tr><td><strong>Dirección del Servicio:</strong></td>"
                "<td>%(location)s</td></tr>"
                "</table>"
                "<p>Por favor, revisa la orden y prepárate para el servicio.</p>"
                "<p>Saludos cordiales,<br/>%(company_name)s</p>"
                "</div>"
            ) % {
                "tech_name": employee.name,
                "order_name": self.name,
                "partner_name": self.partner_id.name,
                "description": self.description or "",
                "date_scheduled": self.date_scheduled or _("Por definir"),
                "priority": priority_label,
                "location": location_text,
                "company_name": self.company_id.name,
            }

            email_from = self.company_id.email or self.env.user.email_formatted
            subject = _("Se te ha asignado la Orden de Trabajo: %s") % self.name

            self.env["mail.mail"].sudo().create(
                {
                    "subject": subject,
                    "body_html": body_html,
                    "email_from": email_from,
                    "email_to": email,
                    "model": self._name,
                    "res_id": self.id,
                    "auto_delete": True,
                }
            )

    def _get_default_stage(self):
        """Obtiene la etapa por defecto de forma robusta y devuelve su id"""
        Stage = self.env["msc.fsm.stage"].sudo()
        # Primero intentar buscar una etapa marcada como por defecto
        stage = Stage.search(
            [
                ("is_default", "=", True),
                ("company_id", "in", [self.env.company.id, False]),
            ],
            limit=1,
        )

        # Si no hay etapa por defecto, buscar por código 'new'
        if not stage:
            stage = Stage.search(
                [
                    ("code", "=", "new"),
                    ("company_id", "in", [self.env.company.id, False]),
                ],
                limit=1,
            )

        # Si tampoco existe, tomar la primera etapa disponible
        if not stage:
            stage = Stage.search(
                [("company_id", "in", [self.env.company.id, False])], limit=1
            )

        return stage.id if stage else False

    @api.depends("date_start", "date_end")
    def _compute_duration(self):
        for record in self:
            if record.date_start and record.date_end:
                delta = record.date_end - record.date_start
                record.duration = delta.total_seconds() / 3600.0
            else:
                record.duration = 0.0

    @api.depends("sale_order_ids")
    def _compute_sale_count(self):
        """Calcula el número de órdenes de venta relacionadas"""
        for record in self:
            record.sale_count = len(record.sudo().sale_order_ids)

    def _compute_access_url(self):
        for record in self:
            record.access_url = f"/my/fsm/{record.id}"

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """Expand stage_ids for kanban view"""
        stage_ids = self.env["msc.fsm.stage"].search(
            [("company_id", "in", [self.env.company.id, False])]
        )
        return stage_ids

    def action_start_work(self):
        """Inicia el trabajo"""
        if self.date_start:
            raise UserError(_("El trabajo ya ha sido iniciado."))

        self.write(
            {
                "date_start": fields.Datetime.now(),
            }
        )

        # Cambiar a etapa "En Progreso" si existe
        progress_stage = self.env["msc.fsm.stage"].search(
            [
                ("code", "=", "progress"),
                ("company_id", "in", [self.env.company.id, False]),
            ],
            limit=1,
        )
        if progress_stage:
            self.stage_id = progress_stage

        return True

    def action_finish_work(self):
        """Finaliza el trabajo"""
        if not self.date_start:
            raise UserError(_("Debe iniciar el trabajo antes de finalizarlo."))

        if self.date_end:
            raise UserError(_("El trabajo ya ha sido finalizado."))

        self.write(
            {
                "date_end": fields.Datetime.now(),
            }
        )

        # Cambiar a etapa "Completado" si existe
        done_stage = self.env["msc.fsm.stage"].search(
            [("code", "=", "done"), ("company_id", "in", [self.env.company.id, False])],
            limit=1,
        )
        if done_stage:
            self.stage_id = done_stage

        return True

    def action_print_order(self):
        """Imprimir orden de trabajo"""
        return self.env.ref("msc_fsm.action_report_fsm_order").report_action(self)

    def action_create_sale_order(self):
        """Crea una orden de venta basada en la orden de trabajo"""
        # Valores básicos para la creación de la orden de venta
        sale_vals = {
            "partner_id": self.partner_id.id,
            "fsm_order_id": self.id,  # Vincular con la orden FSM
            "origin": f'{_("Orden de Trabajo")} - {self.name}',
            "note": self.description,
            "company_id": self.company_id.id,
        }

        # Si hay dirección de servicio, usarla como dirección de entrega
        if self.location_id:
            sale_vals["partner_shipping_id"] = self.location_id.id

        # Add order lines for materials and timesheets
        order_lines = []
        for mat in self.material_line_ids:
            order_lines.append(
                (
                    0,
                    0,
                    {
                        "product_id": mat.product_id.id,
                        "name": mat.name,
                        "product_uom_qty": mat.quantity,
                        "product_uom": mat.uom_id.id,
                    },
                )
            )

        for ts in self.timesheet_line_ids:
            service_product = ts.employee_id.msc_fsm_service_product_id
            if service_product:
                order_lines.append(
                    (
                        0,
                        0,
                        {
                            "product_id": service_product.id,
                            "name": f"{ts.employee_id.name}: {ts.name or service_product.display_name}",
                            "product_uom_qty": ts.duration,
                            "product_uom": service_product.uom_id.id,
                        },
                    )
                )

        if order_lines:
            sale_vals["order_line"] = order_lines

        try:
            sale_order = self.env["sale.order"].create(sale_vals)

            return {
                "type": "ir.actions.act_window",
                "name": _("Orden de Venta"),
                "res_model": "sale.order",
                "res_id": sale_order.id,
                "view_mode": "form",
                "target": "current",
            }
        except Exception as e:
            raise UserError(_("Error al crear la orden de venta: %s") % str(e))

    def action_view_sale_orders(self):
        """Ver órdenes de venta relacionadas"""
        if len(self.sale_order_ids) == 1:
            return {
                "type": "ir.actions.act_window",
                "name": _("Orden de Venta"),
                "res_model": "sale.order",
                "res_id": self.sale_order_ids.id,
                "view_mode": "form",
                "target": "current",
            }
        else:
            return {
                "type": "ir.actions.act_window",
                "name": _("Órdenes de Venta"),
                "res_model": "sale.order",
                "view_mode": "list,form",
                "domain": [("id", "in", self.sale_order_ids.ids)],
                "target": "current",
            }
