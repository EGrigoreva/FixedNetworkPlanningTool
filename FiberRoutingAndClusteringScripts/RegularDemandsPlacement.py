import arcpy
import os
import sys


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


def regular_nodes_placement(area_in, distance_in, spatial_reference_in, name_in, output_gdb_in, output_fds_in):
    """
    This function places the nodes regularly with the specified distance in meters. The input spatial reference shall be 
    the corresponding meters projection to the general (in degrees). The output direction shall be either a database 
    (.gdb) or a feature dataset with the same spatial reference. If the spatial reference is different, the resulting 
    projection will be saved with the same spatial reference as the feature dataset and with no error. This will cause 
    an empty points feature class.

    :param area_in:                 area (cut), where the points will be generated 
    :param distance_in:             distances between the generated points, meters
    :param spatial_reference_in:    spatial reference -> projection coordinate system with meters
    :param output_dir_in:           path to the storing location, either a .gdb or a feature dataset with the 
                                    same projected spatial reference 
    :param name_in:                 name to save the regular nodes as they have to be pushed to different streets for 
                                    each generated topology              
    :return:  path to the generated points
    """

    arcpy.overwriteOutput = 1
    # Project the polygon to projection with meters
    area_proj_path = os.path.join(output_gdb_in, 'area_proj')
    check_exists(area_proj_path)

    # Project_management (in_dataset, out_dataset, out_coor_system, {transform_method}, {in_coor_system},
    # {preserve_shape}, {max_deviation})
    arcpy.Project_management(area_in, area_proj_path, spatial_reference_in)

    # Create fishnet with label points (label points are the MBSs)
    out_feature_class = os.path.join('in_memory', 'points')
    tmp = arcpy.Describe(area_proj_path)
    template = tmp.extent
    origin = '{0} {1}'.format(str(template.XMin), str(template.YMin))
    y_axis = '{0} {1}'.format(str(template.XMin), str(template.YMax))

    # CreateFishnet_management(out_feature_class, origin_coord, y_axis_coord, cell_width, cell_height, number_rows,
    # number_columns, {corner_coord}, {labels}, {template}, {geometry_type})
    points = arcpy.CreateFishnet_management(out_feature_class=out_feature_class,
                                            origin_coord=origin, y_axis_coord=y_axis,
                                            cell_width=distance_in, cell_height=distance_in,
                                            template=template)

    # Clip the label points with the area polygon, in this way only relevant MBSs stay (that are within the area of
    # interest
    # Clip_management (in_raster, rectangle, out_raster, {in_template_dataset}, {nodata_value}, {clipping_geometry},
    # {maintain_clipping_extent})
    points_clip = os.path.join('in_memory', 'points_clip')
    arcpy.Clip_analysis(points[1], area_proj_path, points_clip)

    # Project the generated points back to the original coordinate system
    # Get the original spatial reference
    descript = arcpy.Describe(area_in)
    spatial_ref_orig = descript.spatialReference

    # Project
    points_proj = os.path.join(output_fds_in, '{0}_regular{1}m'.format(name_in, str(distance_in)))
    check_exists(points_proj)

    arcpy.Project_management(points_clip, points_proj, spatial_ref_orig)

    # Delete the area projection
    arcpy.management.Delete(area_proj_path)

    return points_proj


def push_nodes_to_streets(nodes_in, streets_in, name_nodes_in, output_gdb_in, output_fds_in):
    """
    This function pushes the input nodes to the closest input line (street) for the future routing. 
    Shall be done after all the post-processing of the streets to avoid the cycles. 

    :param nodes_in:        input nodes/ points / demands 
    :param streets_in:      input lines/ streets / roads
    :param name_nodes_in:   the name for the output nodes
    :param output_dir_in:   the path, where the pushed nodes will be saved 
    :return:                the path to the result 
    """
    arcpy.overwriteOutput = 1

    # Get the original spatial reference
    descript = arcpy.Describe(nodes_in)
    spatial_ref_orig = descript.spatialReference

    # Calculate the near table -> find the closest line to every point
    out_table = os.path.join(output_gdb_in, 'near_table')
    check_exists(out_table)
    # GenerateNearTable_analysis (in_features, near_features, out_table, {search_radius}, {location}, {angle},
    # {closest}, {closest_count}, {method})
    tmp_table = arcpy.GenerateNearTable_analysis(nodes_in, streets_in, out_table, method='GEODESIC', closest_count=1,
                                                 location='LOCATION')
    # fields = arcpy.ListFields(tmp_table)
    # fc_fields = [field.name for field in fields if field.type != 'Geometry']

    # Create a layer from the pushed points
    out_layer = os.path.join('in_memory', 'tmp')
    tmp_bs = arcpy.MakeXYEventLayer_management(tmp_table, 'NEAR_X', 'NEAR_Y', out_layer,
                                               spatial_ref_orig).getOutput(0)

    # Save pushed points
    out_result = os.path.join(output_fds_in, '{0}_pushed'.format(name_nodes_in))
    check_exists(out_result)
    arcpy.CopyFeatures_management(tmp_bs, out_result)

    # Delete temprorary results
    arcpy.Delete_management(out_table)

    return out_result


def utm_proj(fc_in):
    """
    This function calculates the projection coordinate system. 

    :param fc_in: the feature class  to be projected, feature class

    :return: it returns the string that can be directly translated to a spatial reference
    """
    # arcpy.AddMessage('Calling ' + sys._getframe().f_code.co_name)

    area_extent = arcpy.Describe(fc_in).extent
    y_min = float(area_extent.YMin)
    x_min = float(area_extent.XMin)

    # https://gis.stackexchange.com/questions/224707/calculating-utm-zones-using-arcgis-pro
    zone_tmp = str(int((x_min + 186.0) / 6)) + ('S' if (y_min < 0) else 'N')
    print(str(int((x_min + 186.0) / 6)))
    zone = 'WGS 1984 UTM Zone {0}'.format(zone_tmp)

    return zone


def main(area, streets, spatial_ref_proj, d, output_fds, output_name):

    # Get the gdb path
    descript = arcpy.Describe(output_fds)
    path_full = descript.catalogPath
    output_gdb = os.path.split(path_full)[0]

    arcpy.AddMessage(output_gdb)

    # Place the nodes
    demands_regular_path = regular_nodes_placement(area, d, spatial_ref_proj, output_name, output_gdb, output_fds)

    # Push nodes to streets
    push_nodes_to_streets(demands_regular_path, streets, output_name, output_gdb, output_fds)

    return

if __name__ == '__main__':
    area_in = arcpy.GetParameterAsText(0)
    streets_in = arcpy.GetParameterAsText(1)

    zone_m = utm_proj(area_in)
    spatial_ref_proj_in = arcpy.SpatialReference(zone_m)

    d_in = int(arcpy.GetParameterAsText(2))
    output_fds_in = arcpy.GetParameterAsText(3)
    output_name_in = arcpy.GetParameterAsText(4)

    main(area_in, streets_in, spatial_ref_proj_in, d_in, output_fds_in, output_name_in)