
from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import email_normalize
import re


class GymMember(models.Model):

    _name = 'gym.member'
    _description = 'Gym Member'
    _rec_name = 'name'
    _order = 'registration_date desc'

    # PERSONAL INFORMATION

    name = fields.Char(
        string='Full Name',
        required=True,
        index=True
    )

    birthdate = fields.Date(
        string='Date of Birth'
    )

    gender = fields.Selection(
        [
            ('male', 'Male'),
            ('female', 'Female'),
        ],
        string='Gender'
    )

    phone = fields.Char(string='Phone Number')

    email = fields.Char(string='Email')

    # ADDRESS

    street = fields.Char(string='Street')
    city = fields.Char(string='City')

    # GYM INFORMATION

    registration_date = fields.Date(
        string='Registration Date',
        default=fields.Date.today,
        required=True
    )

    image_1920 = fields.Image(
        string='Profile Picture',
        max_width=1920,
        max_height=1920
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    notes = fields.Text(string='Notes')

    # ODOO USER

    user_id = fields.Many2one(
        'res.users',
        string='Odoo User',
        ondelete='set null',
        index=True
    )

    # COMPUTED FIELD

    age = fields.Integer(
        string='Age',
        compute='_compute_age'
    )

    @api.depends('birthdate')
    def _compute_age(self):
        today = fields.Date.today()

        for member in self:
            if member.birthdate:
                member.age = (
                    today.year - member.birthdate.year
                    - (
                        (today.month, today.day)
                        < (member.birthdate.month, member.birthdate.day)
                    )
                )
            else:
                member.age = 0

    # VALIDATIONS

    @api.constrains('birthdate')
    def _check_birthdate(self):
        for member in self:
            if member.birthdate and member.birthdate > fields.Date.today():
                raise ValidationError(
                    "The date of birth cannot be in the future."
                )

    @api.constrains('email')
    def _check_email(self):
        for member in self:
            if member.email:
                pattern = r'^[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}$'

                if not re.match(pattern, member.email):
                    raise ValidationError(
                        "Please enter a valid email address."
                    )

    _user_id_unique = models.Constraint(
        'UNIQUE(user_id)',
        'An Odoo user can only be linked to one gym member.'
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any('user_id' in vals for vals in vals_list):
            raise AccessError(
                _("The Odoo user account is assigned automatically to each member.")
            )

        with self.env.cr.savepoint():
            members = super().create(vals_list)
            used_logins = set()

            for member in members.filtered(lambda record: not record.user_id):
                login = email_normalize(member.email or '')
                if not login:
                    raise ValidationError(
                        _("An email address is required to create the member's portal account.")
                    )
                if login in used_logins:
                    raise ValidationError(
                        _("Each member must have a unique email address for their portal account.")
                    )
                used_logins.add(login)

                existing_user = self.env['res.users'].sudo().with_context(
                    active_test=False
                ).search([('login', '=ilike', login)], limit=1)
                if existing_user:
                    raise ValidationError(
                        _("The email address %(email)s is already used by an Odoo user.",
                          email=login)
                    )

                member._create_portal_user(login)

        return members

    def _create_portal_user(self, login):
        self.ensure_one()
        partner = self.env['res.partner'].sudo().create({
            'name': self.name,
            'email': login,
            'phone': self.phone,
            'street': self.street,
            'city': self.city,
            'image_1920': self.image_1920,
        })

        user = self.env['res.users'].sudo().with_context(
            no_reset_password=True
        )._create_user_from_template({
            'name': self.name,
            'email': login,
            'login': login,
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            'company_ids': [(6, 0, self.env.company.ids)],
        })
        member_group = self.env.ref('gym_management.group_gym_member')
        user.write({
            'active': self.active,
            'group_ids': [(6, 0, member_group.ids)],
        })
        if self.active:
            self._send_portal_invitation(user)

        self.sudo().write({'user_id': user.id})

    def _send_portal_invitation(self, user):
        template = self.env.ref(
            'auth_signup.portal_set_password_email',
            raise_if_not_found=False,
        )
        if not template:
            raise UserError(
                _("The portal invitation email template is not available.")
            )

        user.partner_id.signup_prepare()
        template.with_context(
            dbname=self.env.cr.dbname,
            lang=user.lang or self.env.lang,
            medium='portalinvite',
            email_notification_force_header=True,
            email_notification_force_footer=True,
            email_notification_subtitles=[_("Your Account"), user.name or ''],
            email_notification_subtitles_highlight_index=1,
            welcome_message=_("Welcome to the gym member portal."),
        ).send_mail(
            user.id,
            force_send=True,
            email_layout_xmlid='mail.mail_notification_layout',
        )

    def write(self, vals):
        if 'user_id' in vals and not self.env.su:
            raise AccessError(
                _("The Odoo user account is managed automatically.")
            )

        result = super().write(vals)
        partner_fields = {'name', 'email', 'phone', 'street', 'city', 'image_1920'}
        if not (partner_fields | {'active'}).intersection(vals):
            return result

        users = self.env['res.users'].sudo().with_context(active_test=False)
        for member in self.filtered('user_id'):
            user_values = {
                field_name: getattr(member, field_name)
                for field_name in partner_fields.intersection(vals)
                if field_name != 'email'
            }
            if 'active' in vals:
                user_values['active'] = member.active
            if 'email' in vals:
                login = email_normalize(member.email or '')
                if not login:
                    raise ValidationError(
                        _("An email address is required for a linked portal account.")
                    )
                duplicate = users.search([
                    ('login', '=ilike', login),
                    ('id', '!=', member.user_id.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError(
                        _("The email address %(email)s is already used by another Odoo user.",
                          email=login)
                    )
                user_values.update({'email': login, 'login': login})

            member.user_id.sudo().write(user_values)
            if member.user_id.active and (
                'email' in vals or ('active' in vals and member.active)
            ):
                member._send_portal_invitation(member.user_id.sudo())

        return result

    def unlink(self):
        portal_users = self.mapped('user_id').sudo()
        result = super().unlink()
        portal_users.write({'active': False})
        return result
