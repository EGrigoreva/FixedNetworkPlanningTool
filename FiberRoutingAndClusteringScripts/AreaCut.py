import arcpy
import os


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


def area_cut(roads_in, widths_in, area_in, output_dir_in, output_name_in):
    """
    This function cuts the input lines feature class (roads, streets, anything) into a square shape around the median 
    point of the input lines feature class. It saves the polygon (the square itself) to the specified output location,
    the cut streets and intersections are saved to the in_memory workspace as they will be further processed afterwords 
    in the graph analysis. 

    :param roads_in:    line feature class that will be cut
    :param widths_in:   the size of the area in meters   
    :param area_in:     the area in km^2 as in the procedural area generation 
    :param output_dir_in:   path, where to save the results
    :param output_name_in: 
    :return: paths to the resulting feature classes - polygon square, lines, intersections
    """
    arcpy.overwriteOutput = 1

    # Transform roads (lines) into a polygon
    area_path = os.path.join('in_memory', 'area')
    check_exists(area_path)

    area = arcpy.FeatureToPolygon_management(roads_in, area_path)

    # Dissolve a multipart polygon
    area_dissolved_path = os.path.join('in_memory', 'area_dissolved')
    check_exists(area_dissolved_path)

    arcpy.Dissolve_management(area, area_dissolved_path)

    # Get central point
    centroid_path = os.path.join('in_memory', 'centroid')
    check_exists(centroid_path)

    arcpy.arcpy.FeatureToPoint_management(area_dissolved_path, centroid_path)

    # Create a circular buffer around with the radius of half of the needed width
    buffer_out = os.path.join('in_memory', 'buffer')
    check_exists(buffer_out)

    width = str(widths_in) + ' Meters'
    arcpy.Buffer_analysis(centroid_path, buffer_out, width)

    # Create a square from the circular buffer
    square_path = os.path.join(output_dir_in, '{0}_area{1}_ply'.format(output_name_in, area_in))
    check_exists(square_path)

    arcpy.FeatureEnvelopeToPolygon_management(buffer_out, square_path)

    # Cut roads
    name_streets_out = os.path.join(output_dir_in, '{0}_area{1}_streets'.format(output_name_in, area_in))
    check_exists(name_streets_out)
    arcpy.Clip_analysis(roads_in, square_path, name_streets_out)

    arcpy.TrimLine_edit(name_streets_out)
    arcpy.TrimLine_edit(name_streets_out)
    arcpy.TrimLine_edit(name_streets_out)

    # Get intersections
    out_feature_class = os.path.join('in_memory', 'intersections_tmp')
    arcpy.Intersect_analysis(name_streets_out, out_feature_class, output_type='POINT')
    arcpy.DeleteIdentical_management(out_feature_class, 'Shape')

    name_intersections_out = os.path.join(output_dir_in, '{0}_area{1}_intersections'.format(output_name_in, area_in))
    check_exists(name_intersections_out)
    arcpy.FeatureToPoint_management(out_feature_class, name_intersections_out)

    return square_path, name_streets_out, name_intersections_out


def main(streets_full, area, output_fds, output_name, buildings=False):

    if area == 1:
        width = 500
    elif area == 4:
        width = 1000
    elif area == 9:
        width = 1500
    elif area == 16:
        width = 2000
    elif area == 25:
        width = 2500
    elif area == 36:
        width = 3000
    elif area == 100:
        width = 5000

    streets_cut_path = area_cut(streets_full, width, area, output_fds, output_name)[1]
    arcpy.AddMessage('The initial area was cut into a square of {0}km^2'.format(area))

    if buildings:
        buildings_path = os.path.join(output_fds, '{0}_area{1}_buildings'.format(output_name, area))
        check_exists(buildings_path)
        arcpy.Clip_analysis(buildings, streets_cut_path, buildings_path)

    return

if __name__ == '__main__':
    streets_full_in = arcpy.GetParameterAsText(0)
    area_in = int(arcpy.GetParameterAsText(2))
    output_fds_in = arcpy.GetParameterAsText(3)
    output_name_in = arcpy.GetParameterAsText(4)

    buildings_in = arcpy.GetParameterAsText(1)

    if buildings_in != '#':
        main(streets_full_in, area_in, output_fds_in, output_name_in, buildings_in)
    else:
        main(streets_full_in, area_in, output_fds_in, output_name_in)