#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import collections
import copy

import six

from heat.common import exception
from heat.common.i18n import _
from heat.engine import function
from heat.engine import template


class CommonTemplate(template.Template):
    """A class of the common implementation for HOT and CFN templates."""

    @classmethod
    def validate_resource_key_type(cls, key, valid_types, typename,
                                   rsrc_name, rsrc_data):
        """Validate the type of the value provided for a specific resource key.

        Used in _validate_resource_definition() to validate correctness of
        user input data.
        """
        if key in rsrc_data:
            if not isinstance(rsrc_data[key], valid_types):
                args = {'name': rsrc_name, 'key': key,
                        'typename': typename}
                message = _('Resource %(name)s %(key)s type '
                            'must be %(typename)s') % args
                raise TypeError(message)
            return True
        else:
            return False

    def _validate_resource_definition(self, name, data):
        """Validate a resource definition snippet given the parsed data."""

        if not self.validate_resource_key_type(self.RES_TYPE,
                                               six.string_types,
                                               'string',
                                               name,
                                               data):
            args = {'name': name, 'type_key': self.RES_TYPE}
            msg = _('Resource %(name)s is missing "%(type_key)s"') % args
            raise KeyError(msg)

        self.validate_resource_key_type(
            self.RES_PROPERTIES,
            (collections.Mapping, function.Function),
            'object', name, data)
        self.validate_resource_key_type(
            self.RES_METADATA,
            (collections.Mapping, function.Function),
            'object', name, data)
        self.validate_resource_key_type(
            self.RES_DEPENDS_ON,
            collections.Sequence,
            'list or string', name, data)
        self.validate_resource_key_type(
            self.RES_DELETION_POLICY,
            (six.string_types, function.Function),
            'string', name, data)
        self.validate_resource_key_type(
            self.RES_UPDATE_POLICY,
            (collections.Mapping, function.Function),
            'object', name, data)
        self.validate_resource_key_type(
            self.RES_DESCRIPTION,
            six.string_types,
            'string', name, data)

    def validate_condition_definitions(self, stack):
        """Check conditions section."""

        resolved_cds = self.resolve_conditions(stack)
        if resolved_cds:
            for cd_key, cd_value in six.iteritems(resolved_cds):
                if not isinstance(cd_value, bool):
                    raise exception.InvalidConditionDefinition(
                        cd=cd_key,
                        definition=cd_value)

    def resolve_conditions(self, stack):
        cd_snippet = self.get_condition_definitions()
        result = {}
        for cd_key, cd_value in six.iteritems(cd_snippet):
            # hasn't been resolved yet
            if not isinstance(cd_value, bool):
                condition_func = self.parse_condition(
                    stack, cd_value)
                resolved_cd_value = function.resolve(condition_func)
                result[cd_key] = resolved_cd_value
            else:
                result[cd_key] = cd_value

        return result

    def get_condition_definitions(self):
        """Return the condition definitions of template."""
        return {}

    def has_condition_section(self, snippet):
        return False

    def get_res_condition(self, stack, res_data, res_name):
        """Return the value of condition referenced by resource."""

        path = ''
        if self.has_condition_section(res_data):
            path = '.'.join([self.RESOURCES, res_name, self.RES_CONDITION])

        return self.get_condition(res_data, stack, path)

    def get_output_condition(self, stack, o_data, o_key):
        path = '.'.join([self.OUTPUTS, o_key, self.OUTPUT_CONDITION])

        return self.get_condition(o_data, stack, path)

    def get_condition(self, snippet, stack, path=''):
        # if specify condition return the resolved condition value,
        # true or false if don't specify condition, return true
        if self.has_condition_section(snippet):
            cd_key = snippet[self.CONDITION]
            cds = self.conditions(stack)
            if cd_key not in cds:
                raise exception.InvalidConditionReference(
                    cd=cd_key, path=path)
            cd = cds[cd_key]
            return cd

        return True

    def conditions(self, stack):
        if self._conditions is None:
            self._conditions = self.resolve_conditions(stack)

        return self._conditions

    def parse_outputs_conditions(self, outputs, stack):
        copy_outputs = copy.deepcopy(outputs)
        for key, snippet in six.iteritems(copy_outputs):
            if self.has_condition_section(snippet):
                cd = self.get_output_condition(stack, snippet, key)
                snippet[self.OUTPUT_CONDITION] = cd
                if not cd:
                    snippet[self.OUTPUT_VALUE] = None

        return copy_outputs
