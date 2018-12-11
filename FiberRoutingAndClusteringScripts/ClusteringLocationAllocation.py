import arcpy
import os
import math


def check_exists(name_in):
    """
    This function check existence of the feature class, which name is specified, and deletes it, if it exists. Some 
    arcpy functions even with the activated overwrite output return errors if the feature class already exists

    :param name_in: check if this file already exists
    :return: 
    """
    if arcpy.Exists(name_in):
        arcpy.Delete_management(name_in)
    return


def get_ids(layer_in):

    ids = []

    # Get fields of points
    field_objects = arcpy.ListFields(layer_in)
    fields = [field.name for field in field_objects if field.type != 'Geometry']

    # Get the nodes ids
    if "OID" in fields:
        points_id = 'OID'

    elif "OBJECTID" in fields:
        points_id = 'OBJECTID'

    elif "ObjectID" in fields:
        points_id = "ObjectID"

    with arcpy.da.SearchCursor(layer_in, points_id) as cursor:
        for row in cursor:
            ids.append(row[0])

    return ids, points_id


def main(network_nd, demands, intersections, facilities, sr, output_fds, output_name, pro, default_cutoff='#'):
    # Check out the Network Analyst extension license
    arcpy.CheckOutExtension("Network")
    # Set overwriting out the files to TRUE
    arcpy.overwriteOutput = 1

    n_demands_in = int(arcpy.GetCount_management(demands).getOutput(0))
    arcpy.AddMessage(n_demands_in)
    number_of_facilities_to_find = int(math.ceil(float(n_demands_in) / float(sr)))
    arcpy.AddMessage(number_of_facilities_to_find)
    arcpy.AddMessage(sr)

    n_nulls = 1

    # Set variables
    layer_name = 'LocAlloc_Clustering'
    impedance_attribute = 'Length'
    problem_type = 'MAXIMIZE_CAPACITATED_COVERAGE'
    line_shape = 'STRAIGHT_LINES'

    while n_nulls != 0:
        #print('Number of facilities to find = {0}'.format(number_of_facilities_to_find))
        if default_cutoff != '#':
            # MakeLocationAllocationLayer_na (in_network_dataset, out_network_analysis_layer, impedance_attribute,
            # {loc_alloc_from_to}, {loc_alloc_problem_type}, {number_facilities_to_find}, {impedance_cutoff},
            # {impedance_transformation}, {impedance_parameter}, {target_market_share}, {accumulate_attribute_name},
            # {UTurn_policy}, {restriction_attribute_name}, {hierarchy}, {output_path_shape}, {default_capacity},
            # {time_of_day})
            # http://desktop.arcgis.com/en/arcmap/10.3/tools/network-analyst-toolbox/make-location-allocation-layer.htm
            result_object = arcpy.na.MakeLocationAllocationLayer(network_nd, layer_name, impedance_attribute,
                                                                 loc_alloc_problem_type=problem_type,
                                                                 number_facilities_to_find=number_of_facilities_to_find,
                                                                 UTurn_policy='NO_UTURNS', output_path_shape=line_shape,
                                                                 default_capacity=sr, impedance_cutoff=default_cutoff)
        else:
            result_object = arcpy.na.MakeLocationAllocationLayer(network_nd, layer_name, impedance_attribute,
                                                                 loc_alloc_problem_type=problem_type,
                                                                 number_facilities_to_find=number_of_facilities_to_find,
                                                                 UTurn_policy='NO_UTURNS', output_path_shape=line_shape,
                                                                 default_capacity=sr)

        # Get the layer object from the result object. The location-allocation layer
        # can now be referenced using the layer object.
        layer_object = result_object.getOutput(0)

        # Get the names of all the sublayers within the location-allocation layer.
        subLayerNames = arcpy.na.GetNAClassNames(layer_object)

        # Stores the layer names that we will use later
        facilities_layer_name = subLayerNames["Facilities"]
        demand_points_layer_name = subLayerNames["DemandPoints"]
        # lines_layer_name = subLayerNames["LALines"]

        arcpy.AddMessage(intersections)
        # Load facilities - Intersections
        if facilities == "Nodes":
            arcpy.na.AddLocations(layer_object, facilities_layer_name, demands)
        else:
            if number_of_facilities_to_find <= n_demands_in:
                arcpy.na.AddLocations(layer_object, facilities_layer_name, intersections)
                arcpy.na.AddLocations(layer_object, facilities_layer_name, intersections)
            else:
                arcpy.na.AddLocations(layer_object, facilities_layer_name, intersections)

        # Load demands - BSs
        arcpy.AddMessage(demands)
        arcpy.na.AddLocations(layer_object, demand_points_layer_name, demands)

        # Solve the location-allocation layer
        arcpy.na.Solve(layer_object)

        # Get the Lines Sublayer (all the distances)
        if pro:
            # lines_sublayer = layer_object.listLayers(lines_layer_name)[0]
            facilities_sublayer_tmp = layer_object.listLayers(facilities_layer_name)[0]
            demands_sublayer_tmp = layer_object.listLayers(demand_points_layer_name)[0]
        elif not pro:
            # lines_sublayer = arcpy.mapping.ListLayers(layer_object, lines_layer_name)[0]
            facilities_sublayer_tmp = arcpy.mapping.ListLayers(layer_object, facilities_layer_name)[0]
            demands_sublayer_tmp = arcpy.mapping.ListLayers(layer_object, demand_points_layer_name)[0]

        facilities_sublayer = os.path.join('in_memory', 'Facilities')
        check_exists(facilities_sublayer)
        arcpy.MakeFeatureLayer_management(facilities_sublayer_tmp, facilities_sublayer)

        # facilities_sublayer_path = os.path.join(r'D:\GISworkspace\Test_for_Scripting.gdb\NewYork_JOCN_big', 'Facilities')
        # arcpy.CopyFeatures_management(facilities_sublayer, facilities_sublayer_path)

        demands_sublayer = os.path.join('in_memory', 'Demands')
        check_exists(demands_sublayer)
        arcpy.MakeFeatureLayer_management(demands_sublayer_tmp, demands_sublayer)

        # demands_sublayer_path = os.path.join(r'D:\GISworkspace\Test_for_Scripting.gdb\NewYork_JOCN_big', 'Demands')
        # arcpy.CopyFeatures_management(demands_sublayer, demands_sublayer_path)

        clause_demands = 'FacilityID IS NULL'
        arcpy.SelectLayerByAttribute_management(demands_sublayer, selection_type='NEW_SELECTION',
                                                where_clause=clause_demands)

        n_nulls = int(arcpy.GetCount_management(demands_sublayer).getOutput(0))
        arcpy.AddMessage(n_nulls)

        number_of_facilities_to_find += 5

    clause_facilities = '"DemandCount" > 1'

    arcpy.SelectLayerByAttribute_management(facilities_sublayer, selection_type='NEW_SELECTION',
                                            where_clause=clause_facilities)

    n_clusters = int(arcpy.GetCount_management(facilities_sublayer).getOutput(0))

    name_cluster_heads = 'Cluster_heads_{0}'.format(output_name)
    out_cluster_heads = os.path.join(output_fds, name_cluster_heads)
    check_exists(out_cluster_heads)
    arcpy.CopyFeatures_management(facilities_sublayer, out_cluster_heads)

    facilities_ids, point_id = get_ids(facilities_sublayer)

    for i in range(len(facilities_ids)):
        clause_facilities = '"{0}" = {1}'.format(point_id, facilities_ids[i])
        arcpy.SelectLayerByAttribute_management(facilities_sublayer, selection_type='NEW_SELECTION',
                                                where_clause=clause_facilities)
        name_cluster_head = 'Cluster_head_{0}_{1}'.format(i, output_name)
        out_cluster_head = os.path.join(output_fds, name_cluster_head)
        check_exists(out_cluster_head)
        arcpy.CopyFeatures_management(facilities_sublayer, out_cluster_head)

        clause_demands = '"FacilityID" = {0}'.format(facilities_ids[i])
        arcpy.SelectLayerByAttribute_management(demands_sublayer, selection_type='NEW_SELECTION',
                                                where_clause=clause_demands)
        name_cluster = 'Cluster_{0}_{1}'.format(i, output_name)
        out_cluster = os.path.join(output_fds, name_cluster)
        check_exists(out_cluster)
        arcpy.CopyFeatures_management(demands_sublayer, out_cluster)

    return n_clusters


if __name__ == '__main__':
    nd_in = r'D:\GISworkspace\Test_for_Scripting.gdb\NewYork_JOCN_big\NewYork_JOCN_big_ND'
    nodes_in = r'D:\GISworkspace\Test_for_Scripting.gdb\NewYork_JOCN_big\bs_to_street'
    intersections_in = r'D:\GISworkspace\Test_for_Scripting.gdb\NewYork_JOCN_big\NewYork_JOCN_big_ND_Junctions'

    output_dir_gdb_in = r'D:\GISworkspace\Test_for_Scripting.gdb'
    output_dir_fc_in = r'D:\GISworkspace\Test_for_Scripting.gdb\NewYork_JOCN_big'

    output_name_in = 'dsl'

    facilities_in = 'Intersections'
    sr_in = 8
    pro_in = False
    default_cutoff_in = 750

    #(network_nd, demands, intersections, facilities, sr, output_fds, output_name, pro, default_cutoff)
    main(nd_in, nodes_in, intersections_in, facilities_in, sr_in, output_dir_fc_in, output_name_in, pro_in,
         default_cutoff_in)