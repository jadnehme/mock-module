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
from viam.utils import struct_to_dict, message_to_struct

# for the mql . Remove as appropriate when fixing the loggin
import bson
from viam.rpc.dial import DialOptions, Credentials
from viam.app.viam_client import ViamClient
import os




class MockModule(Sensor, EasyResource):
    # To enable debug-level logging, either run viam-server with the --debug option,
    # or configure your resource/machine to display debug logs.
    MODEL: ClassVar[Model] = Model(ModelFamily("jad", "mock-module"), "mock-module")

    READINGS_ATTRIBUTE = "readings"
    QUERY_ATTRIBUTE = "query"
    MATCH_ATTRIBUTE = "match"


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
    #mock-module will work with different options. Validate_config checks that the option of having  
    # of having a static list of values to return is correrctly set. This list will be use in the second
    # second option as well to get a MQL return one of the values from the query.
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

      # Check there is the "readings" attributes. No need to check other options as we will use the reading attribute
      # in case of problem with them such as empty result set.
        if not MockModule.READINGS_ATTRIBUTE in config.attributes.fields:
            raise Exception("Missing required attribute 'readings' in config for mock-module")
        
        # we check validity of Readings by making sure And that it does not contain nested JSONs or nested lists.
        config_reading_attr = config.attributes.fields[MockModule.READINGS_ATTRIBUTE]
        if config_reading_attr.HasField("struct_value"):
            for field_name, field_value in config_reading_attr.struct_value.fields.items(): 
                if not field_value.HasField("bool_value") and not field_value.HasField("string_value") and not field_value.HasField("number_value") and not field_value.HasField("list_value"):
                    raise Exception("found unsupported value within config. Only string, number, bools and lists are supported ")
                if field_value.HasField("list_value"):
                    for field_value_item in field_value.list_value.values:
                        if not field_value_item.HasField("bool_value") and not field_value_item.HasField("string_value") and not field_value_item.HasField("number_value"):
                            raise Exception("found unsupported value within config list of values. Only string, number, bools are supported ")


 
        return [], []


    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        """This method allows you to dynamically update your service when it receives a new `config` object.

        Args:
            config (ComponentConfig): The new configuration
            dependencies (Mapping[ResourceName, ResourceBase]): Any dependencies (both required and optional)
        """

        
        reading_config = config.attributes.fields[MockModule.READINGS_ATTRIBUTE]


        # instance variables that will be reset when there is a config change.
        self.reading = {} # the set of reading keys and a list of fallback values as read in the config. Required
        self.counter = 0 # how many times get_reading was called. self.counter is used to iterate through every element of the result set
        self.cache = None # the cached db query result. None means not set. [] means empty result set for the cache
        self.match = None # Predicate of the query. None means not set. Empty means: return everything
        self.project = {} # MLQ $project. Created from the reading config.
        self.api_key = os.getenv("VIAM_API_KEY")  # optional config entry to query DB. Try to read it from the environment first. Can be overridden in config
        self.api_key_id = os.getenv("VIAM_API_KEY_ID")  # optional config entry to query DB. Try to read it from the environment first. Can be overridden in congif.


        # buffer to store the set of possible values for each fieldname
        values = []

        if reading_config.HasField("struct_value"):

            # go through every parameter and populate the list of possible values in an array.
            for field_name, field_value in reading_config.struct_value.fields.items(): 
                values = [] # don't forget to re-initialize it for each attribute
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
                    num_val = field_value.number_value
                    values.append(int(num_val) if num_val.is_integer() else num_val)
                elif field_value.HasField("bool_value"):
                    values.append(field_value.bool_value)
                else:
                    raise Exception("found unsupported value the config within config.  only string, number and bools are supported (no JSON)")
                self.reading[field_name] = values
        # the readings config has only a list of items. 
        elif reading_config.HasField("list_value"):
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
                raise Exception("found unsupported value the config within config.  Only string, number and bools are supported (no JSON)")

            self.reading[None] = values

        
        # if there is a query parameters specified in the config we save the match as well as the project
        # this was useful as the number of parameters started to break the JSON config
        if MockModule.QUERY_ATTRIBUTE in config.attributes.fields:
            query = config.attributes.fields[MockModule.QUERY_ATTRIBUTE]
            self.match = {}
            for field, value in query.struct_value.fields.items():
                if field == "match":
                    self.match = struct_to_dict(value.struct_value)
                if field == "api_key":
                    self.api_key = value.string_value
                if field == "api_key_id":
                    self.api_key_id = value.string_value

            for name in self.reading.keys():
                self.project[name] = f"$data.readings.{name}"



        return super().reconfigure(config, dependencies)

    async def get_readings(
        self,
        *,
        extra: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, SensorReading]:
        
    
        result_dict = {}

        result_size = 0

        # putting the first query in here rather than the reconfig to control the cache
        # this way we can refresh it, update it when we get to the end to get latest elements, 
        # or take chunks at a time etc.
        if self.cache == None:
            viam_client = None
            self.cache = [] # set it to empty as default, in case there's an issue connecting.
            dial_options = DialOptions(
                credentials=Credentials(
                    type="api-key",
                    payload= self.api_key, 
                ),
                auth_entity=self.api_key_id 
                )
            try:
                viam_client = await ViamClient.create_from_dial_options(dial_options)

                # starting the query         
                ## select the columns we want to retrieve from the list of items in the config
                data_client = viam_client.data_client
                if self.match == None:
                    self.cache = await data_client.tabular_data_by_mql(
                            organization_id='8a43a853-48a2-484c-b9aa-c63708df6e2b',
                            mql_binary=[bson.encode({"$project": self.project}),
                                        bson.encode({"$sort": {"time_requested": 1}}),
                                        bson.encode({"$skip": 1}),
                                        bson.encode({"$limit": 5})]
                    )    
                else:
                    self.cache = await data_client.tabular_data_by_mql(
                            organization_id='8a43a853-48a2-484c-b9aa-c63708df6e2b',
                            mql_binary=[bson.encode({"$match": self.match}),
                                        bson.encode({"$project": self.project}),
                                        bson.encode({"$sort": {"time_requested": 1}}),
                                        bson.encode({"$skip": 1}),
                                        bson.encode({"$limit": 5})]
                    )    

            except Exception as e:
                self.logger.error(f"in get_readings trying to connect to DB got error: {e}")
            finally:
                if viam_client is not None:
                    viam_client.close()
                else:
                    self.logger.info("in mock_module.get_readings, error during viam_client creation which was was null at exit. Could not close it")


        if not self.cache == None and not self.cache == []:
            result_dict = self.cache[self.counter % len(self.cache)]



        # if we couldn't or did not query, we use the hardcoded values instead
        if (result_dict == {}):
            for field_name, values in self.reading.items():            
                result_dict[field_name] = values[self.counter % len(values)]

        # Get the next value for iteration.
        self.counter += 1

        return result_dict
        

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

