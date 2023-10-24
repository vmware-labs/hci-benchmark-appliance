# Copyright 2022 (c) VMware, Inc. All rights reserved. -- VMware Confidential
# Derived from pyVim module's sso.SsoAuthenticator and sso.SecurityTokenRequest

import sys
import base64

from pyVim import sso as sts

class SsoAuthenticator(sts.SsoAuthenticator):

    '''
    This class overrides the original SsoAuthenticator in order to
    correctly retrieve a HoK certificate based on username/password
    credentials (instead of cert/privatekey credentials, which is used
    when retrieving tokens for solution users).
    '''

    def get_hok_saml_assertion_for_service_user(self,
                                                username,
                                                password,
                                                public_key,
                                                private_key,
                                                request_duration=60,
                                                token_duration=600,
                                                act_as_token=None,
                                                delegatable=False,
                                                renewable=False,
                                                ssl_context=None):
        '''
        Extracts the assertion from the response received from the Security
        Token Service for service user credentials

        @type          username: C{str}
        @param         username: Username for the service user for which bearer token
                                 needs to be requested.
        @type          password: C{str}
        @param         password: Password for the service user for which bearer token
                                 needs to be requested.
        @type        public_key: C{str}
        @param       public_key: File containing the public key for the service
                                 user registered with SSO, in PEM format.
        @type       private_key: C{str}
        @param      private_key: File containing the private key for the service
                                 user registered with SSO, in PEM format.
        @type  request_duration: C{long}
        @param request_duration: The duration for which the request is valid. If
                                 the STS receives this request after this
                                 duration, it is assumed to have expired. The
                                 duration is in seconds and the default is 60s.
        @type    token_duration: C{long}
        @param   token_duration: The duration for which the SAML token is issued
                                 for. The duration is specified in seconds and
                                 the default is 600s.
        @type      act_as_token: C{str}
        @param     act_as_token: Bearer/Hok token which is delegatable
        @type       delegatable: C{boolean}
        @param      delegatable: Whether the generated token is delegatable or not
        @type         renewable: C{boolean}
        @param        renewable: Whether the generated token is renewable or not
                                 The default value is False
        @type       ssl_context: C{ssl.SSLContext}
        @param      ssl_context: SSL context describing the various SSL options.
                                 It is only supported in Python 2.7.9 or higher.
        @rtype: C{str}
        @return: The SAML assertion in Unicode.
        '''
        request = SecurityTokenRequest(username, password,
                                       public_key, private_key,
                                       request_duration, token_duration)
        soap_message = request.construct_hok_request_for_service_user(delegatable, act_as_token,
                                                                      renewable)
        hok_token = self.perform_request(soap_message, public_key, private_key,
                                         ssl_context)
        return sts.etree.tostring(sts._extract_element(
            sts.etree.fromstring(hok_token), 'Assertion',
            {'saml2': "urn:oasis:names:tc:SAML:2.0:assertion"}),
                              pretty_print=False).decode(sts.UTF_8)


class SecurityTokenRequest(sts.SecurityTokenRequest):

    '''
    This class overrides the original SecurityTokenRequest in order to
    correctly retrieve a HoK certificate based on username/password
    credentials (instead of cert/privatekey credentials, which is used
    when retrieving tokens for solution users).
    '''

    def construct_hok_request_for_service_user(self,
                                               delegatable=False,
                                               act_as_token=None,
                                               renewable=False):
        '''
        Constructs the actual HoK token SOAP request.

        @type   delegatable: C{boolean}
        @param  delegatable: Whether the generated token is delegatable or not
        @type  act_as_token: C{str}
        @param act_as_token: Bearer/Hok token which is delegatable
        @type    renewable: C{boolean}
        @param   renewable: Whether the generated token is renewable or not
                            The default value is False

        @rtype: C{str}
        @return: HoK token SOAP request in Unicode.
        '''
        self._binary_security_token = base64.b64encode(
            sts._extract_certificate(self._public_key)).decode(sts.UTF_8)
        self._use_key = sts.USE_KEY_TEMPLATE % self.__dict__
        self._security_token = (sts.USERNAME_TOKEN_TEMPLATE % self.__dict__) + \
                               (sts.BINARY_SECURITY_TOKEN_TEMPLATE % self.__dict__)
        self._key_type = "http://docs.oasis-open.org/ws-sx/ws-trust/200512/PublicKey"
        self._renewable = str(renewable).lower()
        self._delegatable = str(delegatable).lower()
        self._act_as_token = act_as_token
        if act_as_token is None:
            self._xml_text = sts._canonicalize(sts.REQUEST_TEMPLATE % self.__dict__)
        else:
            self._xml_text = sts.ACTAS_REQUEST_TEMPLATE % self.__dict__
        self.sign_request()
        return sts.etree.tostring(self._xml, pretty_print=False).decode(sts.UTF_8)


