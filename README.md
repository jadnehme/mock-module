# Module mock-module 

The function of this module is to provide a version of a module that allows return of predetermined values for testing purposes.

## Model jad:mock-module:mock-module

The model returns a list of values for a predefined list of keys. The model has two ways of operating: returning a value from a static list defined in the config and obtaining that list from a MQL into Viam's datasource.

### Configuration

The following attribute template can be used to configure this model:

```json
{
"readings": <struct>,
"query": <struct>
}
```

 
#### Attributes

The following attributes are available for this model:

| Name          | Type   | Inclusion | Description                |
|---------------|--------|-----------|----------------------------|
| `readings` | json  | Required  | readings contains the list of keys for which values will be returned. For example: "level": [16,20,25] will return value 16, followed by 20, followed by 25 and starting again at 16 for level. One can put static values as well such as "max_value": 35 |
| `query` | json| optional  | can contain "match" which is the MQL predicate. Only simple filters are supported. One can also overwrite the api_key and api_key_id. If query is not filled or it returns no result mock-module will revert to the static values.|


#### Example Configuration

Only the readings part is required. If using query, readings will be used to get the attributes to extract. The values in readings will also be used as fallbacks in the case where the query fails to return values.
```json
{
  "readings": {
    "component_description": [
      "Black Water tank"
    ],
    "max_L": 1251.5,
    "actual_L": [
      1202,
      1201,
      1199,
      1196,
      1195,
      1200,
      1202
    ],
    "level": [
      16,
      20,
      25,
      27
    ],
    "component_type": [
      "tank"
    ]
  },
  "query": {
    "match": {
      "component_type": "rdk:component:sensor",
      "location_id": "qxlp52u6ql",
      "part_id": "7d2fdd59-04bc-403f-89af-f262cca6d88a",
      "robot_id": "abb77914-08b5-4eb0-a7d4-636d9bb34843",
      "component_name": "mock-sensor-test"
    }
  }
}
```
#### Future work
If this module is useful the following will be done:
1. Support reading from a local file instead of DB.
2. When reaching the end of the cache, update it with latest values. Keep iterating from the same place.
3. A more general solution to 1. : put a limit on the number of items obtained for the cache in one time to protect againts large memory/long queries. Then get the next chunk when we reach the end.
4. Restrict limit MQL match further 
5. Add/check support for some easy and frequent match such as time limitation.

