import arcpy
import math
import os
import json

arcpy.env.overwriteOutput = True


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


def main(network_nd, clustering_allocation, ff_protection, sp_protection, demands, intersections, co, pro, output_dir,
         output_fds, sr_fttb, output_name, brownfield_duct, save_lmf_df, save_clusters):

    import ShortestPathRouting as spr
    planning_result = {}

    facilities = 'Intersections'
    output_name_fttb = '{0}_FTTB_sr{1}'.format(output_name, sr_fttb)

    if clustering_allocation:
        msg = 'Location-Allocation'
    else:
        msg = 'Cost Matrix Penalty Matrix'

    arcpy.AddMessage('Starting clustering with {0} and Splitting Ratio of {1}'.format(msg, sr_fttb))

    if not save_clusters:
        output_fds_cluster = 'in_memory'
    else:
        output_fds_cluster = output_fds

    if clustering_allocation:
        import ClusteringLocationAllocation as clst
        name_clst = output_name_fttb + '_loc'
        clst.main(network_nd, demands, intersections, facilities, sr_fttb, output_fds_cluster, name_clst, pro,'#')

    else:
        import BuildingsClusterCPM as cmpm
        name_clst = output_name_fttb + '_cmpm'
        cmpm.main(network_nd, demands, sr_fttb, intersections, output_fds_cluster, pro, name_clst)

    if not save_clusters:
        name_rns_in = os.path.join('in_memory', 'Cluster_heads_{0}'.format(name_clst))
        name_rns_out = os.path.join(output_fds, 'RemoteNodes_{0}'.format(name_clst))
        check_exists(name_rns_out)

        arcpy.CopyFeatures_management(name_rns_in, name_rns_out)

    arcpy.AddMessage('Clustering was finished, starting with fiber routing with shortest path')

    # Fiber routing: shortest path
    n_nodes = int(arcpy.GetCount_management(demands).getOutput(0))
    n_clusters = int(math.ceil(float(n_nodes) / float(sr_fttb)))
    a = 0
    b = 0
    c = 0

    # LMF
    if brownfield_duct == '#':
        planning_result['lmf'], planning_result['lm_d'], a, b, lmf, c = spr.main(network_nd, n_clusters, 'LMF', co, name_clst,
                                                                         output_fds, pro, save_lmf_df=save_lmf_df,
                                                                         save_clusters=save_clusters)
    else:
        planning_result['lmf'], planning_result['lm_d'], a, b, lmf, c = spr.main(network_nd, n_clusters, 'LMF', co, name_clst,
                                                                         output_fds, pro,
                                                                         brownfield_duct=brownfield_duct,
                                                                         save_lmf_df=save_lmf_df,
                                                                         save_clusters=save_clusters)
    # FF
    if not ff_protection:
        if brownfield_duct == '#':
            planning_result['ff'], planning_result['f_d'], a, b, ff, c = spr.main(network_nd, n_clusters, 'FF', co, name_clst,
                                                                           output_fds, pro, '#',
                                                                           save_clusters=save_clusters)
        else:
            planning_result['ff'], planning_result['f_d'], a, b, ff, c = spr.main(network_nd, n_clusters, 'FF', co, name_clst,
                                                                           output_fds, pro, '#',
                                                                           brownfield_duct=brownfield_duct,
                                                                           save_clusters=save_clusters)
    else:
        if brownfield_duct == '#':
            planning_result['ff'], planning_result['f_d'], \
            planning_result['ff_sp_p'], planning_result['f_d_add_p'], ff, ff_p = spr.main(network_nd, n_clusters, 'FF', co,
                                                                                name_clst, output_fds, pro,
                                                                                ff_protection, sp_protection,
                                                                                save_clusters=save_clusters)
        else:
            planning_result['ff'], planning_result['f_d'], \
            planning_result['ff_sp_p'], planning_result['f_d_add_p'], ff, ff_p = spr.main(network_nd, n_clusters, 'FF', co,
                                                                                name_clst, output_fds, pro,
                                                                                ff_protection, sp_protection,
                                                                                brownfield_duct=brownfield_duct,
                                                                                save_clusters=save_clusters)

    arcpy.AddMessage(planning_result)

    output_file_planning = os.path.join(output_dir, '{0}.txt'.format(output_name))
    f_p = open(output_file_planning, 'w')
    json.dump(planning_result, f_p)

    # Save total fibers and ducts to be used as brownfield for further scenarios
    total_fiber = os.path.join(output_fds, 'Total_fiber_{0}'.format(output_name_fttb))
    check_exists(total_fiber)

    if not ff_protection:
        arcpy.Merge_management([lmf, ff], total_fiber)
    else:
        arcpy.Merge_management([lmf, ff, ff_p], total_fiber)

    arcpy.AddGeometryAttributes_management(total_fiber, 'LENGTH_GEODESIC', 'METERS')

    total_duct = os.path.join(output_fds, 'Total_duct_{0}'.format(output_name_fttb))
    check_exists(total_duct)
    arcpy.Dissolve_management(total_fiber, total_duct)

    arcpy.AddGeometryAttributes_management(total_duct, 'LENGTH_GEODESIC', 'METERS')

    return


if __name__ == '__main__':

    from_pycharm = False

    if not from_pycharm:
        network_nd_in = arcpy.GetParameterAsText(0)

        clustering_allocation_in = bool(arcpy.GetParameterAsText(1))

        ff_protection_in = bool(arcpy.GetParameterAsText(2))
        sp_protection_in = bool(arcpy.GetParameterAsText(3))

        sr_fttb_in = int(arcpy.GetParameterAsText(4))

        demands_in = arcpy.GetParameterAsText(5)

        intersections_in = arcpy.GetParameterAsText(6)
        co_in = arcpy.GetParameterAsText(7)

        save_lmf_df_in = bool(arcpy.GetParameterAsText(8))
        save_clusters_in = bool(arcpy.GetParameterAsText(9))

        brownfield_duct_in = arcpy.GetParameterAsText(10)
        if not brownfield_duct_in:
            brownfield_duct_in = '#'

        output_dir_in = arcpy.GetParameterAsText(11)
        output_fds_in = arcpy.GetParameterAsText(12)
        output_name_in = arcpy.GetParameterAsText(13)

    else:
        network_nd_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun_toy_example\Ottobrun_toy_example_ND'

        clustering_allocation_in = True

        ff_protection_in = True
        sp_protection_in = True

        sr_fttb_in = 8

        demands_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun_toy_example\BSs_regular1000m_toy_example'

        intersections_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun_toy_example\Ottobrun_intersections_toy_example'
        co_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun_toy_example\CO_Ottobrun_toy_example'

        save_lmf_df_in = False

        brownfield_duct_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun_toy_example_p2p\SP_FF_Test_p2p'

        output_dir_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018'
        output_fds_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun_toy_example_fttb'
        output_name_in = 'mbs_test_bf'

    pro_in = False

    main(network_nd_in, clustering_allocation_in, ff_protection_in, sp_protection_in, demands_in, intersections_in, co_in, pro_in,
         output_dir_in, output_fds_in, sr_fttb_in, output_name_in, brownfield_duct_in, save_lmf_df_in, save_clusters_in)


