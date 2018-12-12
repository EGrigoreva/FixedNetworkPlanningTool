import arcpy
import os
import json

arcpy.env.overwriteOutput = True


########################################################################################################################
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


########################################################################################################################
def main(network_nd, ff_protection, sp_protection, demands, co, pro, output_dir, output_fds, output_name,
         brownfield_duct):

    import ShortestPathRouting as spr

    planning_result = {}

    # Fiber routing: shortest path
    n_nodes = int(arcpy.GetCount_management(demands).getOutput(0))
    output_name_p2p = output_name

    if not ff_protection:
        if brownfield_duct == '#':
            planning_result['fiber'], planning_result['duct'], a, b, ff, c = spr.main(network_nd, n_nodes, 'FF', co,
                                                                               output_name_p2p, output_fds, pro,
                                                                               ff_protection, p2p_demands=demands)
        else:
            planning_result['fiber'], planning_result['duct'], a, b, ff, c = spr.main(network_nd, n_nodes, 'FF', co,
                                                                               output_name_p2p, output_fds, pro,
                                                                               ff_protection, p2p_demands=demands,
                                                                               brownfield_duct=brownfield_duct)
    else:
        if brownfield_duct == '#':
            planning_result['fiber'], planning_result['duct'], planning_result['fiber_p'], \
            planning_result['duct_add_p'], ff, ff_p = spr.main(network_nd, n_nodes, 'FF', co, output_name_p2p, output_fds,
                                                     pro, ff_protection, sp_protection, p2p_demands=demands)
        else:
            planning_result['fiber'], planning_result['duct'], planning_result['fiber_p'], \
            planning_result['duct_add_p'], ff, ff_p = spr.main(network_nd, n_nodes, 'FF', co, output_name_p2p, output_fds,
                                                     pro, ff_protection, sp_protection, p2p_demands=demands,
                                                     brownfield_duct=brownfield_duct)

    arcpy.AddMessage(planning_result)

    output_file_planning = os.path.join(output_dir, '{0}.txt'.format(output_name))
    f_p = open(output_file_planning, 'w')
    json.dump(planning_result, f_p)

    # Save total fibers and ducts to be used as brownfield for further scenarios
    total_fiber = os.path.join(output_fds, 'Total_fiber_{0}'.format(output_name_p2p))
    check_exists(total_fiber)

    if ff_protection:
        arcpy.Merge_management([ff, ff_p], total_fiber)
        arcpy.AddGeometryAttributes_management(total_fiber,'LENGTH_GEODESIC', 'METERS')

    total_duct = os.path.join(output_fds, 'Total_duct_{0}'.format(output_name_p2p))
    check_exists(total_duct)
    arcpy.Dissolve_management(total_fiber, total_duct)

    arcpy.AddGeometryAttributes_management(total_duct, 'LENGTH_GEODESIC', 'METERS')

    return


########################################################################################################################
if __name__ == '__main__':

    from_pycharm = False

    if not from_pycharm:
        network_nd_in = arcpy.GetParameterAsText(0)

        ff_protection_in = bool(arcpy.GetParameterAsText(1))
        sp_protection_in = bool(arcpy.GetParameterAsText(2))

        demands_in = arcpy.GetParameterAsText(3)

        co_in = arcpy.GetParameterAsText(4)

        brownfield_duct_in = arcpy.GetParameterAsText(5)
        if not brownfield_duct_in:
            brownfield_duct_in = '#'

        output_dir_in = arcpy.GetParameterAsText(6)
        output_fds_in = arcpy.GetParameterAsText(7)
        output_name_in = arcpy.GetParameterAsText(8)

    else:
        network_nd_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun\Ottobrun_ND'

        ff_protection_in = True
        sp_protection_in = False

        demands_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun\BSs_pushed'

        co_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun\CO_Ottobrun'

        brownfield_duct_in = r''

        output_dir_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018'
        output_fds_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun_test'
        output_name_in = r'P2P_test_protection_duct_min'

    pro_in = False

    main(network_nd_in, ff_protection_in, sp_protection_in, demands_in, co_in, pro_in, output_dir_in, output_fds_in,
         output_name_in, brownfield_duct_in)
