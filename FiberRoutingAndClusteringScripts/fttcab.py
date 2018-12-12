import arcpy
import math
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
def main(network_nd, lines, ff_protection, sp_protection, demands, intersections,
         co, sr_fttcab_rn, sr_fttcab_b_dsl, dsl_reach, output_dir, output_fds, output_name, pro, copper_routes=False,
         brownfield_duct='#', save_lmf_df=False, save_clusters=False):

    import ShortestPathRouting as spr
    planning_result = {}

    facilities = 'Intersections'

    arcpy.AddMessage('Starting clustering with {0} and Splitting Ratio of the Remote Node 1 (Power Splitter) of '
                     '{1} and the Splitting ration of the Remote Node 2 (DSLAM) of {2}'.format('Location-Allocation',
                                                                                               sr_fttcab_rn,
                                                                                               sr_fttcab_b_dsl))
    arcpy.AddMessage('Clustering for the demands with the cut-off for the DSL last mile.')

    if not save_clusters:
        output_fds_cluster = 'in_memory'
    else:
        output_fds_cluster = output_fds

    # Getting RN2 (ONUs in this case) locations: clustering the buildings with DSL splitting ratio
    output_name_dsl_build = 'FTTCab_RN2_{0}_cutoff{1}_dsl'.format(sr_fttcab_b_dsl, dsl_reach)
    # (network_nd, demands, intersections, facilities, sr, output_fds, output_name, pro, default_cutoff)

    import ClusteringLocationAllocation as clst
    name_clst = output_name_dsl_build + '_loc'
    n_clusters_copper = clst.main(network_nd, demands, intersections, facilities, sr_fttcab_b_dsl, output_fds_cluster,
                                  name_clst, pro, dsl_reach, lines)
    print(n_clusters_copper)

    name_onus = 'Cluster_heads_{0}'.format(name_clst)
    rns2 = os.path.join(output_fds_cluster, name_onus)

    if not save_clusters:
        cabinets = os.path.join(output_fds, 'Cabinets_{0}'.format(name_clst))
        check_exists(cabinets)
        arcpy.CopyFeatures_management(rns2, cabinets)

    arcpy.AddMessage('Clustering to the cabinets was finished, starting with the clustering to the RN1')

    # Clustering the buildings with fiber SR, possible RN2 positions (PSs in this case) are the RN2 positions from
    # the DSL case
    output_name_fiber = 'FTTCab_RN1_{0}_fiber'.format(sr_fttcab_rn)
    n_clusters_cab = clst.main(network_nd, rns2, intersections, facilities, sr_fttcab_rn, output_fds_cluster,
                               output_name_fiber, pro)

    if not save_clusters:
        name_rns = 'Cluster_heads_{0}'.format(output_name_fiber)
        rns1 = os.path.join(output_fds_cluster, name_rns)

        rns = os.path.join(output_fds, 'RemoteNodes_{0}'.format(output_name_fiber))
        check_exists(rns)
        arcpy.CopyFeatures_management(rns1, rns)

    arcpy.AddMessage('Clustering was finished, starting with fiber routing with shortest path')

    # LMF
    a = 0
    b = 0
    c = 0

    if copper_routes:
        planning_result['copper'], planning_result['copper_d'], a, b, copper, c = spr.main(network_nd, n_clusters_copper, 'LMF', co,
                                                                                name_clst, output_fds, pro,
                                                                                save_lmf_df=True,
                                                                                save_clusters=save_clusters)

    #DF
    if brownfield_duct == '#':
        planning_result['df'], planning_result['d_d'], a, b, df, c = spr.main(network_nd, n_clusters_cab, 'DF', co,
                                                                       output_name_fiber, output_fds, pro,
                                                                       save_lmf_df=save_lmf_df,
                                                                       save_clusters=save_clusters)
    else:
        planning_result['df'], planning_result['d_d'], a, b, df, c = spr.main(network_nd, n_clusters_cab, 'DF', co,
                                                                       output_name_fiber, output_fds, pro,
                                                                       brownfield_duct=brownfield_duct,
                                                                       save_lmf_df=save_lmf_df,
                                                                       save_clusters=save_clusters)

    #FF
    if not ff_protection:
        if brownfield_duct == '#':
            planning_result['ff'], planning_result['f_d'], a, b, ff, c = spr.main(network_nd, 1, 'FF', co, output_name_fiber,
                                                                       output_fds, pro)
        else:
            planning_result['ff'], planning_result['f_d'], a, b, ff, c = spr.main(network_nd, 1, 'FF', co, output_name_fiber,
                                                                           output_fds, pro,
                                                                           brownfield_duct=brownfield_duct,
                                                                           save_clusters=save_clusters)
    else:
        if brownfield_duct == '#':
            planning_result['ff'], planning_result['f_d'], \
            planning_result['ff_sp_p'], planning_result['f_d_add_p'], ff, ff_p = spr.main(network_nd, 1, 'FF', co, output_name_fiber,
                                                                                output_fds, pro, ff_protection,
                                                                                sp_protection,
                                                                                save_clusters=save_clusters)
        else:
            planning_result['ff'], planning_result['f_d'], \
            planning_result['ff_sp_p'], planning_result['f_d_add_p'], ff, ff_p  = spr.main(network_nd, 1, 'FF', co,
                                                                                output_name_fiber,
                                                                                output_fds, pro, ff_protection,
                                                                                sp_protection,
                                                                                brownfield_duct=brownfield_duct,
                                                                                save_clusters=save_clusters)

    arcpy.AddMessage(planning_result)

    output_file_planning = os.path.join(output_dir, '{0}.txt'.format(output_name))
    f_p = open(output_file_planning, 'w')
    json.dump(planning_result, f_p)

    # Save total fibers and ducts to be used as brownfield for further scenarios
    total_fiber = os.path.join(output_fds, 'Total_fiber_{0}'.format(output_name_fiber))
    check_exists(total_fiber)

    if not ff_protection:
        arcpy.Merge_management([df, ff], total_fiber)

    else:
        arcpy.Merge_management([df, ff, ff_p], total_fiber)

    arcpy.AddGeometryAttributes_management(total_fiber, 'LENGTH_GEODESIC', 'METERS')

    total_duct = os.path.join(output_fds, 'Total_duct_{0}'.format(output_name_fiber))
    check_exists(total_duct)
    arcpy.Dissolve_management(total_fiber, total_duct)

    arcpy.AddGeometryAttributes_management(total_duct, 'LENGTH_GEODESIC', 'METERS')

    return


########################################################################################################################
if __name__ == '__main__':

    from_pycharm = False

    if not from_pycharm:
        network_nd_in = arcpy.GetParameterAsText(0)

        lines_in = arcpy.GetParameterAsText(1)

        ff_protection_in = bool(arcpy.GetParameterAsText(2))
        sp_protection_in = bool(arcpy.GetParameterAsText(3))

        sr_fttcab_b_dsl_in = int(arcpy.GetParameterAsText(4))
        dsl_reach_in = int(arcpy.GetParameterAsText(5))
        copper_routes_in = bool(arcpy.GetParameterAsText(6))

        sr_fttcab_rn_in = int(arcpy.GetParameterAsText(7))
        demands_in = arcpy.GetParameterAsText(8)

        intersections_in = arcpy.GetParameterAsText(9)
        co_in = arcpy.GetParameterAsText(10)

        save_lmf_df_in = bool(arcpy.GetParameterAsText(11))
        save_clusters_in = bool(arcpy.GetParameterAsText(12))

        brownfield_duct_in = arcpy.GetParameterAsText(13)
        if not brownfield_duct_in:
            brownfield_duct_in = '#'

        output_dir_in = arcpy.GetParameterAsText(14) #r'D:\GISworkspace\ITSplanning' #
        output_fds_in = arcpy.GetParameterAsText(15)
        output_name_in = arcpy.GetParameterAsText(16)  #'test' #

    else:
        network_nd_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun\Ottobrun_ND'

        ff_protection_in = True
        sp_protection_in = True

        demands_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun\BSs_pushed'

        intersections_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun\Ottobrun_ND_Junctions'
        co_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun\CO_Ottobrun'

        brownfield_duct_in = r''

        sr_fttcab_rn_in = 16

        sr_fttcab_b_dsl_in = 4
        dsl_reach_in = 1000

        copper_routes_in = False

        output_dir_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018'
        output_fds_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun_fttcab'
        output_name_in = 'test_fttcab'

    pro_in = False

    main(network_nd_in, lines_in, ff_protection_in, sp_protection_in, demands_in, intersections_in,
         co_in, sr_fttcab_rn_in, sr_fttcab_b_dsl_in, dsl_reach_in, output_dir_in, output_fds_in, output_name_in, pro_in,
         copper_routes_in, brownfield_duct_in, save_lmf_df_in, save_clusters_in)