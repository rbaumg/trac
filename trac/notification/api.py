# -*- coding: utf-8 -*-
#
# Copyright (C) 2003-2014 Edgewall Software
# Copyright (C) 2003-2005 Daniel Lundin <daniel@edgewall.com>
# Copyright (C) 2005-2006 Emmanuel Blot <emmanuel.blot@free.fr>
# Copyright (C) 2008 Stephen Hansen
# Copyright (C) 2009 Robert Corsaro
# Copyright (C) 2010-2012 Steffen Hoffmann
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://trac.edgewall.org/wiki/TracLicense.
#
# This software consists of voluntary contributions made by many
# individuals. For the exact contribution history, see the revision
# history and logs, available at http://trac.edgewall.org/log/.

from trac.config import BoolOption, ExtensionOption, ListOption, Option
from trac.core import *
from trac.util.compat import set


__all__ = ['IEmailAddressResolver', 'IEmailDecorator', 'IEmailSender',
           'INotificationDistributor', 'INotificationFormatter',
           'NotificationEvent', 'NotificationSystem', 'get_target_id']


class INotificationDistributor(Interface):
    """Deliver events over some transport (i.e. messaging protocol)."""

    def transports(self):
        """Return a list of supported transport names."""

    def distribute(self, transport, recipients, event):
        """Distribute the notification event.

        :param transport: the name of a supported transport
        :param recipients: a list of (sid, authenticated, address, format)
                           tuples, where either `sid` or `address` can be
                           `None`
        :param event: a `NotificationEvent`
        """


class INotificationFormatter(Interface):
    """Convert events into messages appropriate for a given transport."""

    def get_supported_styles(self, transport):
        """Return a list of supported styles.

        :param transport: the name of a transport
        :return: a list of tuples (style, realm)
        """

    def format(self, transport, style, event):
        """Convert the event to an appropriate message.

        :param transport: the name of a transport
        :param style: the name of a supported style
        :return: The return type of this method depends on transport and must
                 be compatible with the `INotificationDistributor` that
                 handles messages for this transport.
        """


class IEmailAddressResolver(Interface):
    """Map sessions to email addresses."""

    def get_address_for_session(self, sid, authenticated):
        """Map a session id and authenticated flag to an e-mail address.

        :param sid: the session id
        :param authenticated: 1 for authenticated sessions, 0 otherwise
        :return: an email address or `None`
        """


class IEmailDecorator(Interface):
    def decorate_message(self, event, message, charset):
        """Manipulate the message before it is sent on it's way.

        :param event: a `NotificationEvent`
        :param message: an `email.message.Message` to manipulate
        :param charset: the `email.charset.Charset` to use
        """


class IEmailSender(Interface):
    """Extension point interface for components that allow sending e-mail."""

    def send(self, from_addr, recipients, message):
        """Send message to recipients."""


def get_target_id(target):
    """Extract the resource ID from event targets.

    :param target: a resource model (e.g. `Ticket` or `WikiPage`)
    :return: the resource ID
    """
    # Common Trac resource.
    if hasattr(target, 'id'):
        return str(target.id)
    # Wiki page special case.
    elif hasattr(target, 'name'):
        return target.name
    # Last resort: just stringify.
    return str(target)


class NotificationEvent(object):
    """All data related to a particular notification event.

    :param realm: the resource realm (e.g. 'ticket' or 'wiki')
    :param category: the kind of event that happened to the resource
                     (e.g. 'created', 'changed' or 'deleted')
    :param target: the resource model (e.g. Ticket or WikiPage) or `None`
    :param time: the `datetime` when the event happened
    """

    def __init__(self, realm, category, target, time, author=""):
        self.realm = realm
        self.category = category
        self.target = target
        self.time = time
        self.author = author


class NotificationSystem(Component):

    email_sender = ExtensionOption('notification', 'email_sender',
                                   IEmailSender, 'SmtpEmailSender',
        """Name of the component implementing `IEmailSender`.

        This component is used by the notification system to send emails.
        Trac currently provides `SmtpEmailSender` for connecting to an SMTP
        server, and `SendmailEmailSender` for running a `sendmail`-compatible
        executable. (''since 0.12'')""")

    smtp_enabled = BoolOption('notification', 'smtp_enabled', 'false',
        """Enable email notification.""")

    smtp_from = Option('notification', 'smtp_from', 'trac@localhost',
        """Sender address to use in notification emails.

        At least one of `smtp_from` and `smtp_replyto` must be set, otherwise
        Trac refuses to send notification mails.""")

    smtp_from_name = Option('notification', 'smtp_from_name', '',
        """Sender name to use in notification emails.""")

    smtp_from_author = BoolOption('notification', 'smtp_from_author', 'false',
        """Use the author of the change as the sender in notification emails
           (e.g. reporter of a new ticket, author of a comment). If the
           author hasn't set an email address, `smtp_from` and
           `smtp_from_name` are used instead.
           (''since 1.0'')""")

    smtp_replyto = Option('notification', 'smtp_replyto', 'trac@localhost',
        """Reply-To address to use in notification emails.

        At least one of `smtp_from` and `smtp_replyto` must be set, otherwise
        Trac refuses to send notification mails.""")

    smtp_always_cc_list = ListOption(
        'notification', 'smtp_always_cc', '', sep=(',', ' '),
        doc="""Comma-separated list of email addresses to always send
               notifications to. Addresses can be seen by all recipients
               (Cc:).""")

    smtp_always_bcc_list = ListOption(
        'notification', 'smtp_always_bcc', '', sep=(',', ' '),
        doc="""Comma-separated list of email addresses to always send
            notifications to. Addresses are not public (Bcc:).
            """)

    smtp_default_domain = Option('notification', 'smtp_default_domain', '',
        """Default host/domain to append to addresses that do not specify
           one. Fully qualified addresses are not modified. The default
           domain is appended to all username/login for which an email
           address cannot be found in the user settings.""")

    ignore_domains_list = ListOption('notification', 'ignore_domains', '',
        doc="""Comma-separated list of domains that should not be considered
           part of email addresses (for usernames with Kerberos domains).""")

    admit_domains_list = ListOption('notification', 'admit_domains', '',
        doc="""Comma-separated list of domains that should be considered as
        valid for email addresses (such as localdomain).""")

    mime_encoding = Option('notification', 'mime_encoding', 'none',
        """Specifies the MIME encoding scheme for emails.

        Supported values are: `none`, the default value which uses 7-bit
        encoding if the text is plain ASCII or 8-bit otherwise. `base64`,
        which works with any kind of content but may cause some issues with
        touchy anti-spam/anti-virus engine. `qp` or `quoted-printable`,
        which works best for european languages (more compact than base64) if
        8-bit encoding cannot be used.
        """)

    use_public_cc = BoolOption('notification', 'use_public_cc', 'false',
        """Addresses in the To and Cc fields are visible to all recipients.

        If this option is disabled, recipients are put in the Bcc list.
        """)

    use_short_addr = BoolOption('notification', 'use_short_addr', 'false',
        """Permit email address without a host/domain (i.e. username only).

        The SMTP server should accept those addresses, and either append
        a FQDN or use local delivery. See also `smtp_default_domain`. Do not
        use this option with a public SMTP server.
        """)

    smtp_subject_prefix = Option('notification', 'smtp_subject_prefix',
                                 '__default__',
        """Text to prepend to subject line of notification emails.

        If the setting is not defined, then `[$project_name]` is used as the
        prefix. If no prefix is desired, then specifying an empty option
        will disable it.
        """)

    distributors = ExtensionPoint(INotificationDistributor)

    @property
    def smtp_always_cc(self):  # For backward compatibility
        return self.config.get('notification', 'smtp_always_cc')

    @property
    def smtp_always_bcc(self):  # For backward compatibility
        return self.config.get('notification', 'smtp_always_bcc')

    @property
    def ignore_domains(self):  # For backward compatibility
        return self.config.get('notification', 'ignore_domains')

    @property
    def admit_domains(self):  # For backward compatibility
        return self.config.get('notification', 'admit_domains')

    def send_email(self, from_addr, recipients, message):
        """Send message to recipients via e-mail."""
        self.email_sender.send(from_addr, recipients, message)

    def distribute_event(self, event, subscriptions):
        """Distribute a event to all subscriptions.

        :param event: a `NotificationEvent`
        :param subscriptions: a list of tuples (sid, authenticated, address,
                              transport, format) where either sid or
                              address can be `None`
        """
        packages = {}
        for sid, authenticated, address, transport, format in subscriptions:
            package = packages.setdefault(transport, set())
            package.add((sid, authenticated, address, format))
        for distributor in self.distributors:
            for transport in distributor.transports():
                if transport in packages:
                    recipients = list(packages[transport])
                    distributor.distribute(transport, recipients, event)

