from typing import (Any, ClassVar, Dict, Final, List, Mapping, Optional,
                    Sequence, Tuple)

from typing_extensions import Self

from viam.components.sensor import *
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import Geometry, ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.utils import SensorReading, ValueTypes


class MockModule(Sensor, EasyResource):
    # To enable debug-level logging, either run viam-server with the --debug option,
    # or configure your resource/machine to display debug logs.
    MODEL: ClassVar[Model] = Model(ModelFamily("jad", "mock-module"), "mock-module")

    READINGS_ATTRIBUTE = "readings"
    QUERY_ATTRIBUTE = "query"


    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> Self:
        """This method creates a new instance of this Sensor component.
        The default implementation sets the name from the `config` parameter and then calls `reconfigure`.

        Args:
            config (ComponentConfig): The configuration for this resource
            dependencies (Mapping[ResourceName, ResourceBase]): The dependencies (both required and optional)

        Returns:
            Self: The resource
        """

        return super().new(config, dependencies)

    @classmethod
    #mock-module will work with different options. Validate_config checks that at least one of them is set.
    # the most common use case is to have a static list of reading values. One of which will be returned.
    # the second option (to be implemented) is to get a MQL or SQL and return one of the values from the query.
    # implementation will iterate through the values.
    # large config may break so an external config file may be needed. To be determined during testing.
    def validate_config(
        cls, config: ComponentConfig
    ) -> Tuple[Sequence[str], Sequence[str]]:
        """This method allows you to validate the configuration object received from the machine,
        as well as to return any required dependencies or optional dependencies based on that `config`.

        Args:
            config (ComponentConfig): The configuration for this resource

        Returns:
            Tuple[Sequence[str], Sequence[str]]: A tuple where the
                first element is a list of required dependencies and the
                second element is a list of optional dependencies
        """
        
        if not MockModule.READINGS_ATTRIBUTE in config.attributes.fields:
            raise Exception("Missing required attribute 'readings' in config for mock-module")
        
 
        return [], []


    '''First time (reconfigure)
- require that config has a valid predicate clause that matches what we save, such as:

  "query" : {
    "location_id" : "qxlp52u6ql",
    "robot_id" : "abb77914-08b5-4eb0-a7d4-636d9bb34843",
    "part_id" : "7d2fdd59-04bc-403f-89af-f262cca6d88a",
    "component_name ": "mock-sensor-test",
    "component_type ": "rdk:component:sensor",
    "time_received_min": "2025-06-29T21:17:33.413Z",
    "time_received_max": "2025-06-30T21:17:33.413Z"
  },

1- Transform it in predicacate and surround it by the SQL elements (or, better, the MQL)

WHERE location_id:’qxlp52u6ql' AND robot_id='abb77914-08b5-4eb0-a7d4-636d9bb34843' AND part_id='7d2fdd59-04bc-403f-89af-f262cca6d88a' AND component_name='mock-sensor-test' AND component_type='rdk:component:sensor' AND time_received_min >= CAST('2025-06-29T21:17:33.413Z' AS TIMESTAMP) and time_received_max <= CAST('2025-06-29T21:17:33.413Z' AS TIMESTAMP) 

2 count the number of elements
SELECT count(*) FROM readings WHERE location_id='qxlp52u6ql' AND robot_id='abb77914-08b5-4eb0-a7d4-636d9bb34843' AND part_id='7d2fdd59-04bc-403f-89af-f262cca6d88a' AND component_name='mock-sensor-test' AND component_type='rdk:component:sensor' AND time_received >= CAST('2025-06-29T21:17:33.413Z' AS TIMESTAMP)
SELECT data.readings FROM readings 

3-save state:
- Save count in self.number_records . 
- set iteration = 0

4- update get_redaings by calling: SELECT data.readings FROM readings WHERE location_id='qxlp52u6ql' AND robot_id='abb77914-08b5-4eb0-a7d4-636d9bb34843' AND part_id='7d2fdd59-04bc-403f-89af-f262cca6d88a' AND component_name='mock-sensor-test' AND component_type='rdk:component:sensor' AND time_received >= CAST('2025-06-29T21:17:33.413Z' AS TIMESTAMP) ORDER BY time_received asc limit 1 offset self.iteration%self.number_records
self.iteration +=1
Note: if count is 0 we should just return an empty value 
if the count is 1, we could have a cash the call after the first time (first time, check if we have a cash)
also possible: get chunks which we go through
we could also get the entire data set and replay it. Or at least get a chunk.
'''
    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        """This method allows you to dynamically update your service when it receives a new `config` object.

        Args:
            config (ComponentConfig): The new configuration
            dependencies (Mapping[ResourceName, ResourceBase]): Any dependencies (both required and optional)
        """

        
        self.config = config.attributes.fields[MockModule.READINGS_ATTRIBUTE]
        self.counter = 0

        self.reading = {}
        values = []
    
        if self.config.HasField("struct_value"):

            # to do: make this recursive so that we support any JSON
            # go through every parameter and populate the list of possible values in an array.
            for field_name, field_value in self.config.struct_value.fields.items():
                values = [] # don't forget to re-initialize it.
                # Each field_value is another protobuf Value message (we do not support embedded JSON)
                if field_value.HasField("list_value"):
                    # Extract values from the list

                    for item in field_value.list_value.values:
                        if item.HasField("string_value"):
                            values.append(item.string_value)
                        elif item.HasField("number_value"):
                            values.append(int(item.number_value) if item.number_value.is_integer() else item.number_value)
                        elif item.HasField("bool_value"):
                            values.append(item.bool_value)

                elif field_value.HasField("string_value"):
                    values.append(field_value.string_value)
                elif field_value.HasField("number_value"):
                    num_val = [field_value.number_value]
                    values.append(int(num_val) if num_val.is_integer() else num_val)
                elif field_value.HasField("bool_value"):
                    values.append(field_value.bool_value)
                else:
                    raise Exception("found unsupported value the config within config.  only string, number and bools are supported (no JSON)")

                    
            self.reading[field_name] = values
        # the readings config has only a list of items. 
        elif self.config.HasField("list_value"):
            for item in field_value.list_value.values:
                if item.HasField("string_value"):
                    values.append(item.string_value)
                elif item.HasField("number_value"):
                    values.append(int(item.number_value) if item.number_value.is_integer() else item.number_value)
                elif item.HasField("bool_value"):
                    values.append(item.bool_value)
                else:
                    raise Exception("found unsupported value the config within config.  only string, number and bools are supported (no JSON)")

            self.reading[None] = values
        # readings has only one value. Create an array of one to always return it for simplicity.
        else:
            if item.HasField("string_value"):
                values.append(item.string_value)
            elif item.HasField("number_value"):
                values.append(int(item.number_value) if item.number_value.is_integer() else item.number_value)
            elif item.HasField("bool_value"):
                values.append(item.bool_value)
            else:
                raise Exception("found unsupported value the config within config.  only string, number and bools are supported (no JSON)")

            self.reading[None] = values

        print(f"config reading is {self.reading}" )

        
        # the query parameters are specified in the config.
        if MockModule.QUERY_ATTRIBUTE in config.attributes.fields:
            self.query = config.attributes.fields[MockModule.QUERY_ATTRIBUTE]



        if config.attributes
        print(f"Reconfigured and set counter to {self.counter}")

        return super().reconfigure(config, dependencies)

    async def get_readings(
        self,
        *,
        extra: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, SensorReading]:
        
        result_dict = {}

    
        if self.readings.HasField("struct_value"):
            struct_data = self.readings.struct_value

        
            for field_name, field_value in struct_data.fields.items():
                # Each field_value is another protobuf Value message
                if field_value.HasField("list_value"):
                    # Extract values from the list
                    values = []
                    for item in field_value.list_value.values:
                        if item.HasField("string_value"):
                            values.append(item.string_value)
                        elif item.HasField("number_value"):
                            values.append(int(item.number_value) if item.number_value.is_integer() else item.number_value)
                        elif item.HasField("bool_value"):
                            values.append(item.bool_value)
                    
                    # If list has only one item, extract it; otherwise keep as list
                    if len(values) == 1:
                        result_dict[field_name] = values[0]
                    else: # we want to return one of the values from the list
                        result_dict[field_name] = values [self.counter % len(values)]
                
                elif field_value.HasField("string_value"):
                    result_dict[field_name] = field_value.string_value
                elif field_value.HasField("number_value"):
                    num_val = field_value.number_value
                    result_dict[field_name] = int(num_val) if num_val.is_integer() else num_val
                elif field_value.HasField("bool_value"):
                    result_dict[field_name] = field_value.bool_value
            self.counter += 1
        else:
            result_dict = {
                "readings" : self.config.string_value
            }
        return result_dict
        
        

        return { "readings": self.readings }

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, ValueTypes]:
        self.logger.error("`do_command` is not implemented")
        raise NotImplementedError()

    async def get_geometries(
        self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None
    ) -> List[Geometry]:
        self.logger.error("`get_geometries` is not implemented")
        raise NotImplementedError()

