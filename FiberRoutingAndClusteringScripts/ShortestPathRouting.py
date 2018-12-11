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


def check_object_id(layer_in):
    """
    
    :param layer_in:    the layer, where we are not sure how the field is named 
    :return: the name  of the field
    """
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

    return points_id


def post_processing_fiber(routes_all_in, ff_routes_protection='#'):

    field_name = check_object_id(routes_all_in)
    arcpy.AddGeometryAttributes_management(routes_all_in, 'LENGTH_GEODESIC', 'METERS')

    dissolved_name = os.path.join('in_memory', 'dissolved_all')

    check_exists(dissolved_name)

    # Dissolve_management (in_features, out_feature_class, {dissolve_field}, {statistics_fields}, {multi_part},
    # {unsplit_lines})
    arcpy.Dissolve_management(routes_all_in, dissolved_name, field_name, statistics_fields="LENGTH_GEO SUM")

    arcpy.AddGeometryAttributes_management(dissolved_name, 'LENGTH_GEODESIC', 'METERS')

    with arcpy.da.SearchCursor(dissolved_name, ['SUM_LENGTH_GEO', 'LENGTH_GEO']) as rows:
        for row in rows:
            fiber_w = row[0]  # fiber length
            duct_w = row[1]  # duct length

            fiber_p = 0
            duct_w_p = 0

    if ff_routes_protection != '#':
        field_name_p = check_object_id(ff_routes_protection)
        arcpy.AddGeometryAttributes_management(ff_routes_protection, 'LENGTH_GEODESIC', 'METERS')


        dissolved_name_p = os.path.join('in_memory', 'dissolved_p')

        check_exists(dissolved_name_p)

        arcpy.Dissolve_management(routes_all_in, dissolved_name, field_name_p, statistics_fields="LENGTH_GEO SUM")

        with arcpy.da.SearchCursor(dissolved_name, 'SUM_LENGTH_GEO') as rows:
            for row in rows:
                fiber_p = row[0]  # fiber length

        merge_routes_name = os.path.join('in_memory', 'merged_w_p')
        check_exists(merge_routes_name)

        arcpy.Merge_management([routes_all_in, ff_routes_protection], merge_routes_name)

        dissolve_name_additional_duct = os.path.join('in_memory', 'dissolved_w_p')
        check_exists(dissolve_name_additional_duct)
        field_name_w_p = check_object_id(merge_routes_name)
        arcpy.Dissolve_management(merge_routes_name, dissolve_name_additional_duct, field_name_w_p)
        arcpy.AddGeometryAttributes_management(dissolve_name_additional_duct, 'LENGTH_GEODESIC', 'METERS')

        with arcpy.da.SearchCursor(dissolve_name_additional_duct, 'LENGTH_GEO') as rows:
            for row in rows:
                duct_w_p = row[0]  # fiber length

    return fiber_w, duct_w, fiber_p, duct_w_p - duct_w


def route_fiber(nd_in, incidents_in, facilities_in, name_in, output_fc_in, pro_in, protection_in=False,
                sp_protection_in=True, brownfield_duct='#'):
    arcpy.CheckOutExtension('Network')

    # Set local variables
    layer_name = "ClosestFacility"
    impedance = "Length"

    # MakeClosestFacilityLayer_na (in_network_dataset, out_network_analysis_layer, impedance_attribute,
    # {travel_from_to}, {default_cutoff}, {default_number_facilities_to_find}, {accumulate_attribute_name},
    # {UTurn_policy}, {restriction_attribute_name}, {hierarchy}, {hierarchy_settings}, {output_path_shape},
    # {time_of_day}, {time_of_day_usage})
    #
    # http://desktop.arcgis.com/en/arcmap/10.3/tools/network-analyst-toolbox/make-closest-facility-layer.htm
    result_object = arcpy.na.MakeClosestFacilityLayer(nd_in, layer_name, impedance, 'TRAVEL_TO', default_cutoff=None,
                                                      default_number_facilities_to_find=1,
                                                      output_path_shape='TRUE_LINES_WITH_MEASURES')

    # Get the layer object from the result object. The Closest facility layer can
    # now be referenced using the layer object.
    layer_object = result_object.getOutput(0)

    # Get the names of all the sublayers within the Closest facility layer.
    sublayer_names = arcpy.na.GetNAClassNames(layer_object)

    # Stores the layer names that we will use later
    incidents_layer_name = sublayer_names["Incidents"]  # as origins
    facilities_layer_name = sublayer_names["Facilities"]  # as destinations
    lines_layer_name = sublayer_names["CFRoutes"]  # as lines

    arcpy.na.AddLocations(layer_object, incidents_layer_name, incidents_in)
    arcpy.na.AddLocations(layer_object, facilities_layer_name, facilities_in)

    if brownfield_duct != '#':
        mapping = "Name Name #;Attr_Length # " + '0,001' + "; BarrierType # 1"
        arcpy.na.AddLocations(layer_object, "Line Barriers", brownfield_duct, mapping, search_tolerance="5 Meters")

    # Solve the Closest facility  layer
    arcpy.na.Solve(layer_object)

    # # Save the solved Closest facility layer as a layer file on disk
    # output_layer_file = os.path.join(output_dir_in, layer_name)
    # arcpy.MakeFeatureLayer_management(layer_object, output_layer_file)

    # Get the Lines Sublayer (all the distances)
    if pro_in:
        lines_sublayer = layer_object.listLayers(lines_layer_name)[0]
    elif not pro_in:
        lines_sublayer = arcpy.mapping.ListLayers(layer_object, lines_layer_name)[0]

    layer_out_path = os.path.join(output_fc_in, name_in)
    arcpy.management.CopyFeatures(lines_sublayer, layer_out_path)

    protection_out_path = "#"

    # If requested route the protection paths
    if protection_in:
        # For all the routed apths the disjoint path has to be found
        n_paths = int(arcpy.GetCount_management(incidents_in).getOutput(0))

        field_objects = arcpy.ListFields(layer_out_path)
        fields = [field.name for field in field_objects if field.type != 'Geometry']

        if 'Total_Length' in fields:
            field_len = 'Total_Length'
        elif 'Shape_Length' in fields:
            field_len = 'Shape_Length'

        # Iterate through all the facility-demand pairs and their respective routes
        cursor_r = arcpy.da.SearchCursor(layer_out_path, ['SHAPE@', field_len])
        cursor_n = arcpy.da.SearchCursor(incidents_in, 'SHAPE@')

        if sp_protection_in:
            name_protect = 'sp'
        else:
            name_protect = 'duct_sharing'

        protection_out_path = os.path.join(output_fc_in, '{0}_protection_{1}'.format(name_in, name_protect))
        check_exists(protection_out_path)
        arcpy.CreateFeatureclass_management(output_fc_in, '{0}_protection_{1}'.format(name_in, name_protect),
                                            template=layer_out_path)

        for i in range(n_paths):
            path = cursor_r.next()
            node = cursor_n.next()
            if not path[1] == 0:
                if sp_protection_in:
                    tmp = protection_routing(nd_in, facilities_in, node[0], path[0], pro_in)
                    # Add the protection route to the output feature class
                    arcpy.Append_management(tmp, protection_out_path, schema_type="NO_TEST")
                else:
                    all_paths = os.path.join('in_memory', 'all_paths_{0}'.format(i))
                    check_exists(all_paths)
                    arcpy.CopyFeatures_management(layer_out_path, all_paths)

                    other_paths_tmp = os.path.join('in_memory', 'other_paths_{0}_dissolved'.format(i))
                    check_exists(other_paths_tmp)
                    arcpy.Dissolve_management(all_paths, other_paths_tmp)

                    other_paths = os.path.join('in_memory', 'other_paths_{0}'.format(i))
                    check_exists(other_paths)
                    arcpy.FeatureToLine_management(other_paths_tmp, other_paths)

                    other_paths_layer = os.path.join('in_memory', 'other_paths_layer_{0}'.format(i))
                    check_exists(other_paths_layer)
                    arcpy.MakeFeatureLayer_management(other_paths, other_paths_layer)

                    arcpy.SelectLayerByLocation_management(other_paths_layer, 'SHARE_A_LINE_SEGMENT_WITH', path[0],
                                                           selection_type='NEW_SELECTION',
                                                           invert_spatial_relationship='INVERT')

                    scaled_cost = os.path.join('in_memory', 'scaled_cost_{0}'.format(i))
                    check_exists(scaled_cost)
                    arcpy.CopyFeatures_management(other_paths_layer, scaled_cost)

                    tmp = protection_routing(nd_in, facilities_in, node[0], path[0], pro_in, scaled_cost)
                    # Add the protection route to the output feature class
                    arcpy.Append_management(tmp, protection_out_path, schema_type="NO_TEST")

    return layer_out_path, protection_out_path


def protection_routing(nd_in, start_in, end_in, route_in, pro_in, other_routes='#'):
    """
    This function finds a disjoint path between given start-end node pars to the given existing working path. 
    The general procedure is the same as for the fiber routing but with additional constraint (line barrier) and thus 
    restricted on one node pair (facility-demand).

    :param nd_in: network dataset on which the shortest path routing is done, network dataset
    :param start_in: starting node, feature class
    :param end_in: end node, feature class
    :param route_in: working path, feature class
    :param pro_in: if the script is executed in arcgis pro, binary

    :return: the resulting line layer -> path
    """
    # Set local variables
    layer_name = "ClosestFacility"
    impedance = "Length"

    # MakeClosestFacilityLayer_na (in_network_dataset, out_network_analysis_layer, impedance_attribute,
    # {travel_from_to}, {default_cutoff}, {default_number_facilities_to_find}, {accumulate_attribute_name},
    # {UTurn_policy}, {restriction_attribute_name}, {hierarchy}, {hierarchy_settings}, {output_path_shape},
    # {time_of_day}, {time_of_day_usage})
    #
    # http://desktop.arcgis.com/en/arcmap/10.3/tools/network-analyst-toolbox/make-closest-facility-layer.htm
    result_object = arcpy.na.MakeClosestFacilityLayer(nd_in, layer_name, impedance, 'TRAVEL_TO', default_cutoff=None,
                                                      default_number_facilities_to_find=1,
                                                      output_path_shape='TRUE_LINES_WITH_MEASURES')

    # Get the layer object from the result object. The Closest facility layer can
    # now be referenced using the layer object.
    layer_object = result_object.getOutput(0)

    # Get the names of all the sublayers within the Closest facility layer.
    sublayer_names = arcpy.na.GetNAClassNames(layer_object)

    # Stores the layer names that we will use later
    incidents_layer_name = sublayer_names["Incidents"]  # as origins
    facilities_layer_name = sublayer_names["Facilities"]  # as destinations
    lines_layer_name = sublayer_names["CFRoutes"]  # as lines

    arcpy.na.AddLocations(layer_object, incidents_layer_name, end_in)
    arcpy.na.AddLocations(layer_object, facilities_layer_name, start_in)

    # Cost attribute for disjoint paths
    sc_tmp1 = 10000000000

    # Add the cost upscaled working path to the restrictions as the scaled cost
    mapping = "Name Name #;Attr_Length # " + str(sc_tmp1) + "; BarrierType # 1"
    arcpy.na.AddLocations(layer_object, "Line Barriers", route_in, mapping, search_tolerance="5 Meters")

    # Add the downscaled other duct if required
    if other_routes != '#':
        mapping = "Name Name #;Attr_Length # " + '0,001' + "; BarrierType # 1"
        arcpy.na.AddLocations(layer_object, "Line Barriers", other_routes, mapping, search_tolerance="5 Meters")

    # Solve the Closest facility  layer
    arcpy.na.Solve(layer_object)

    # # Save the solved Closest facility layer as a layer file on disk
    # output_layer_file = os.path.join(output_dir_in, layer_name)
    # arcpy.MakeFeatureLayer_management(layer_object, output_layer_file)

    # Get the Lines Sublayer (all the distances)
    if pro_in:
        lines_sublayer = layer_object.listLayers(lines_layer_name)[0]
    elif not pro_in:
        lines_sublayer = arcpy.mapping.ListLayers(layer_object, lines_layer_name)[0]

    return lines_sublayer


def main(network_nd, n_clusters, stage, co, name, output_fds, pro, ff_protection=False,
         sp_protection_in=True, p2p_demands='#', brownfield_duct='#', save_lmf_df=False, save_clusters=False):

    routes_all_list = []
    path_out_p = 0

    if not save_clusters:
        output_clusters = 'in_memory'
    else:
        output_clusters = output_fds

    if stage == 'LMF' or stage == 'DF':
        if not save_lmf_df:
            output_lmf_df = 'in_memory'

        else:
            output_lmf_df = output_fds

        for i in range(n_clusters):
            cluster = os.path.join(output_clusters, 'Cluster_{0}_{1}'.format(i, name))
            cluster_head = os.path.join(output_clusters, 'Cluster_head_{0}_{1}'.format(i, name))
            name_out = 'SP_{0}_{1}_{2}'.format(stage, i, name)
            check_exists(os.path.join(output_lmf_df, name_out))

            if brownfield_duct != '#':
                route = route_fiber(network_nd, cluster, cluster_head, name_out, output_lmf_df, pro,
                                    brownfield_duct=brownfield_duct)
            else:
                route = route_fiber(network_nd, cluster, cluster_head, name_out, output_lmf_df, pro)

            routes_all_list.append(route)

        path_out = os.path.join(output_fds, 'SP_{0}_{1}_all_fiber'.format(stage, name))
        check_exists(path_out)
        routes_all = arcpy.Merge_management(routes_all_list, path_out)

        fiber_w, duct_w, fiber_p, duct_p = post_processing_fiber(routes_all)

    elif stage == 'FF':
        if p2p_demands == '#':
            cluster = os.path.join(output_clusters, 'Cluster_heads_{0}'.format(name))
        else:
            cluster = p2p_demands

        name_out = 'SP_{0}_{1}'.format(stage, name)
        check_exists(os.path.join('in_memory', name_out))

        if not ff_protection:
            if brownfield_duct == '#':
                ff_routes = route_fiber(network_nd, cluster, co, name_out, output_fds, pro)[0]
            else:
                ff_routes = route_fiber(network_nd, cluster, co, name_out, output_fds, pro,
                                        brownfield_duct=brownfield_duct)[0]
            fiber_w, duct_w, fiber_p, duct_p = post_processing_fiber(ff_routes)

            path_out = ff_routes
        else:
            if brownfield_duct == '#':
                ff_routes, ff_routes_protection = route_fiber(network_nd, cluster, co, name_out, output_fds, pro,
                                                              ff_protection, sp_protection_in)
            else:
                ff_routes, ff_routes_protection = route_fiber(network_nd, cluster, co, name_out, output_fds, pro,
                                                              ff_protection, sp_protection_in,
                                                              brownfield_duct=brownfield_duct)
            path_out = ff_routes
            path_out_p = ff_routes_protection

            fiber_w, duct_w, fiber_p, duct_p = post_processing_fiber(ff_routes, ff_routes_protection)

    return fiber_w, duct_w, fiber_p, duct_p, path_out, path_out_p

if __name__ == '__main__':
    nd = r'D:\GISworkspace\GeographyModelsEvaluation_INPUT.gdb\TEST\TEST_ND'
    co_in = r'D:\GISworkspace\GeographyModelsEvaluation_INPUT.gdb\TEST\co_random'
    demands_in = r'D:\GISworkspace\GeographyModelsEvaluation_INPUT.gdb\TEST\regular_test_pushed'

    output_dir = r'D:\GISworkspace\GeographyModelsEvaluation_INPUT.gdb\TEST'
    facilities_in = 'Intersections'
    sr_in = 8
    pro_in = False

    name_out_in = 'Test'
    main(nd, demands_in, co_in, facilities_in, sr_in, name_out_in, output_dir, pro_in)