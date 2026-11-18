from unittest.mock import patch

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGymMemberPortalAccount(TransactionCase):

    def test_create_member_generates_portal_user_and_invitation(self):
        with patch.object(
            type(self.env['mail.template']),
            'send_mail',
            return_value=1,
        ) as send_mail:
            member = self.env['gym.member'].create({
                'name': 'Gym Member Test',
                'email': 'Member.Test@example.com',
            })

        user = member.user_id
        member_group = self.env.ref('gym_management.group_gym_member')
        portal_group = self.env.ref('base.group_portal')
        internal_group = self.env.ref('base.group_user')

        self.assertTrue(user)
        self.assertEqual(user.login, 'member.test@example.com')
        self.assertEqual(user.email, 'member.test@example.com')
        self.assertIn(member_group, user.group_ids)
        self.assertIn(portal_group, user.all_group_ids)
        self.assertNotIn(internal_group, user.all_group_ids)
        self.assertEqual(user.partner_id.name, member.name)
        send_mail.assert_called_once()

    def test_member_requires_email_for_automatic_portal_account(self):
        with self.assertRaises(ValidationError):
            with self.env.cr.savepoint():
                self.env['gym.member'].create({'name': 'No Email'})

        self.assertFalse(
            self.env['gym.member'].search([('name', '=', 'No Email')])
        )

    def test_member_user_link_cannot_be_supplied_manually(self):
        with self.assertRaises(AccessError):
            self.env['gym.member'].create({
                'name': 'Manually Linked Member',
                'email': 'manual@example.com',
                'user_id': self.env.user.id,
            })

    def test_member_updates_keep_portal_contact_in_sync(self):
        with patch.object(
            type(self.env['mail.template']),
            'send_mail',
            return_value=1,
        ) as send_mail:
            member = self.env['gym.member'].create({
                'name': 'Member Before Update',
                'email': 'before@example.com',
            })
            member.write({
                'name': 'Member After Update',
                'email': 'after@example.com',
                'phone': '555-0100',
            })

        self.assertEqual(member.user_id.name, 'Member After Update')
        self.assertEqual(member.user_id.login, 'after@example.com')
        self.assertEqual(member.user_id.email, 'after@example.com')
        self.assertEqual(member.user_id.phone, '555-0100')
        self.assertEqual(send_mail.call_count, 2)

    def test_member_activation_controls_portal_account(self):
        with patch.object(
            type(self.env['mail.template']),
            'send_mail',
            return_value=1,
        ) as send_mail:
            member = self.env['gym.member'].create({
                'name': 'Activation Test Member',
                'email': 'activation@example.com',
            })
            member.write({'active': False})
            self.assertFalse(member.user_id.active)
            member.write({'active': True})

        self.assertTrue(member.user_id.active)
        self.assertEqual(send_mail.call_count, 2)

    def test_deleting_member_deactivates_portal_account(self):
        with patch.object(
            type(self.env['mail.template']),
            'send_mail',
            return_value=1,
        ):
            member = self.env['gym.member'].create({
                'name': 'Deleted Member',
                'email': 'deleted@example.com',
            })

        user = member.user_id
        member.unlink()

        self.assertFalse(user.active)

    def test_portal_user_can_read_only_their_own_member_record(self):
        with patch.object(
            type(self.env['mail.template']),
            'send_mail',
            return_value=1,
        ):
            member = self.env['gym.member'].create({
                'name': 'First Portal Member',
                'email': 'first.portal@example.com',
            })
            other_member = self.env['gym.member'].create({
                'name': 'Second Portal Member',
                'email': 'second.portal@example.com',
            })

        member_model = self.env['gym.member'].with_user(member.user_id)
        self.assertEqual(member_model.search([]).ids, member.ids)
        with self.assertRaises(AccessError):
            member_model.browse(other_member.id).read(['name'])
        with self.assertRaises(AccessError):
            member_model.check_access_rights('write')

    def test_duplicate_email_does_not_create_second_member_or_user(self):
        with patch.object(
            type(self.env['mail.template']),
            'send_mail',
            return_value=1,
        ):
            self.env['gym.member'].create({
                'name': 'First Member',
                'email': 'duplicate@example.com',
            })

            with self.assertRaises(ValidationError):
                with self.env.cr.savepoint():
                    self.env['gym.member'].create({
                        'name': 'Second Member',
                        'email': 'DUPLICATE@example.com',
                    })

        self.assertEqual(
            self.env['gym.member'].search_count([
                ('email', '=ilike', 'duplicate@example.com'),
            ]),
            1,
        )
        self.assertEqual(
            self.env['res.users'].sudo().with_context(active_test=False).search_count([
                ('login', '=ilike', 'duplicate@example.com'),
            ]),
            1,
        )

    def test_receptionist_can_manage_members_and_coach_is_read_only(self):
        users = self.env['res.users'].sudo().with_context(no_reset_password=True)
        receptionist = users.create({
            'name': 'Gym Receptionist Test',
            'login': 'receptionist.test',
            'group_ids': [(6, 0, self.env.ref(
                'gym_management.group_gym_receptionist'
            ).ids)],
        })
        coach = users.create({
            'name': 'Gym Coach Test',
            'login': 'coach.test',
            'group_ids': [(6, 0, self.env.ref(
                'gym_management.group_gym_coach'
            ).ids)],
        })

        self.env['gym.member'].with_user(receptionist).check_access_rights('create')
        self.env['gym.member'].with_user(receptionist).check_access_rights('write')
        self.env['gym.member'].with_user(receptionist).check_access_rights('unlink')
        self.env['gym.member'].with_user(coach).check_access_rights('read')
        with self.assertRaises(AccessError):
            self.env['gym.member'].with_user(coach).check_access_rights('create')
        with self.assertRaises(AccessError):
            self.env['gym.member'].with_user(coach).check_access_rights('write')
