import arcpy
import sys
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
def main(network_nd, clustering_allocation, ff_protection, sp_protection, buildings, intersections, co, sr_rn1, sr_rn2,
         output_dir, output_fds, output_name, joint_planning=False, bs='#', sc='#', sc_wdm='#', brownfield_duct='#',
         save_lmf_df=False, save_clusters=False):

    pro = False

    ####################################################################################################################
    # TDM demands clustering
    facilities = 'Intersections'
    output_name_rn2 = 'HPON_RN2_sr{0}'.format(sr_rn2)

    if not save_clusters:
        output_fds_cluster = 'in_memory'
    else:
        output_fds_cluster = output_fds

    if clustering_allocation:
        msg = 'Location-Allocation'
    else:
        msg = 'Cost Matrix Penalty Matrix'

    arcpy.AddMessage('Starting clustering of the second level demands (TDM demands) with {0} and Splitting '
                     'Ratio of {1}'.format(msg, sr_rn2))

    if joint_planning and sc != '#' and not sc_wdm:
        arcpy.AddMessage('TDM demands include buildings and Small Cells (SCs)')

        demands = os.path.join('in_memory', 'Buildings_and_small_cells')
        check_exists(demands)
        arcpy.Merge_management([buildings, sc], demands)

        if clustering_allocation:
            import ClusteringLocationAllocation as clst
            name_clst_lmf = output_name_rn2 + '_build_and_sc_loc'
            n_clusters_lmf = clst.main(network_nd, demands, intersections, facilities, sr_rn2, output_fds_cluster,
                                       name_clst_lmf, pro, '#')

        else:
            import BuildingsClusterCPM as cmpm
            name_clst_lmf = output_name_rn2 + '_build_and_sc_cmpm'
            n_clusters_lmf = cmpm.main(network_nd, demands, sr_rn2, intersections, output_fds_cluster, pro, name_clst_lmf)
    else:
        if clustering_allocation:
            import ClusteringLocationAllocation as clst
            name_clst_lmf = output_name_rn2 + '_build_loc'
            n_clusters_lmf = clst.main(network_nd, buildings, intersections, facilities, sr_rn2, output_fds_cluster, name_clst_lmf,
                                       pro)
        else:
            import BuildingsClusterCPM as cmpm
            name_clst_lmf = output_name_rn2 + '_build_cmpm'
            n_clusters_lmf = cmpm.main(network_nd, buildings, sr_rn2, intersections, output_fds_cluster, pro, name_clst_lmf)

    ####################################################################################################################
    # WDM demands clustering

    arcpy.AddMessage('Clustering of the second stage demands was finished, starting with clustering of the first stage '
                     'demands with Location-Allocation and Splitting Ratio of {0}'.format(sr_rn1))

    import ClusteringLocationAllocation as clst

    output_name_rn1 = 'HPON_RN1_sr{0}'.format(sr_rn1)

    name_onus = 'Cluster_heads_{0}'.format(name_clst_lmf)
    rns2 = os.path.join(output_fds_cluster, name_onus)

    # Save the cluster heads
    rn2_out_path = os.path.join(output_fds, name_clst_lmf)
    check_exists(rn2_out_path)
    arcpy.CopyFeatures_management(rns2, rn2_out_path)

    # Base stations, small cells and power splitters
    if joint_planning and sc != '#' and sc_wdm:
        arcpy.AddMessage('WDM demands include Base Stations (BSs), Small Cells (SCs) and Remote Nodes 2 (RN2)')

        demands = os.path.join('in_memory', 'all_wdm_demands')
        check_exists(demands)
        arcpy.Merge_management([rns2, sc, bs], demands)

        field_objects = arcpy.ListFields(demands)
        fields = [field.name for field in field_objects if field.type != 'Geometry']
        if 'Weight' in fields:
            arcpy.DeleteField_management(demands, 'Weight')

        name_clst_df = output_name_rn1 + '_bs_sc_rn2_loc'
        n_clusters_df = clst.main(network_nd, demands, intersections, facilities, sr_rn1, output_fds_cluster,
                                  name_clst_df, pro, '#')

    # Base stations and power splitters
    elif joint_planning and sc != '#' and not sc_wdm:
        arcpy.AddMessage('WDM demands include Base Stations (BSs) and Remote Nodes 2 (RN2)')

        demands = os.path.join('in_memory', 'all_wdm_demands')
        check_exists(demands)
        arcpy.Merge_management([rns2, bs], demands)

        field_objects = arcpy.ListFields(demands)
        fields = [field.name for field in field_objects if field.type != 'Geometry']
        if 'Weight' in fields:
            arcpy.DeleteField_management(demands, 'Weight')

        name_clst_df = output_name_rn1 + '_bs_rn2_loc'
        n_clusters_df = clst.main(network_nd, demands, intersections, facilities, sr_rn1, output_fds_cluster,
                                  name_clst_df, pro, '#')

    # Only residential users
    else:
        arcpy.AddMessage('First level demands include only Remote Nodes 2 (RN2)')
        name_clst_df = output_name_rn1 + '_rn2_loc'

        n_clusters_df = clst.main(network_nd, rns2, intersections, facilities, sr_rn1, output_fds_cluster,
                                  name_clst_df, pro, '#')

    # Save the cluster heads
    name_rns1 = 'Cluster_heads_{0}'.format(name_clst_df)
    rns1 = os.path.join(output_fds_cluster, name_rns1)

    rn1_out_path = os.path.join(output_fds, name_clst_df)
    check_exists(rn1_out_path)
    arcpy.CopyFeatures_management(rns1, rn1_out_path)

    import ShortestPathRouting as spr
    planning_result = {}

    # LMF
    a = 0
    b = 0
    c = 0

    planning_result['lmf'], planning_result['lm_d'], a, b, lmf, c = spr.main(network_nd, n_clusters_lmf, 'LMF', co,
                                                                             name_clst_lmf, output_fds, pro,
                                                                             brownfield_duct=brownfield_duct,
                                                                             save_lmf_df=save_lmf_df,
                                                                             save_clusters=save_clusters)

    #DF
    planning_result['df'], planning_result['d_d'], a, b, df, c = spr.main(network_nd, n_clusters_df, 'DF', co,
                                                                          name_clst_df, output_fds, pro,
                                                                          brownfield_duct=brownfield_duct,
                                                                          save_lmf_df=save_lmf_df,
                                                                          save_clusters=save_clusters)

    #FF
    if not ff_protection:
        planning_result['ff'], planning_result['f_d'], a, b, ff, c = spr.main(network_nd, 1, 'FF', co, name_clst_df,
                                                                              output_fds, pro,
                                                                              brownfield_duct=brownfield_duct,
                                                                              save_clusters=save_clusters)
    else:
        planning_result['ff'], planning_result['f_d'], \
        planning_result['ff_sp_p'], planning_result['f_d_add_p'], ff, ff_p = spr.main(network_nd, 1, 'FF', co,
                                                                                      name_clst_df,
                                                                                      output_fds, pro, ff_protection,
                                                                                      sp_protection,
                                                                                      brownfield_duct=brownfield_duct,
                                                                                      save_clusters=save_clusters)

    arcpy.AddMessage(planning_result)

    output_file_planning = os.path.join(output_dir, '{0}.txt'.format(output_name))
    f_p = open(output_file_planning, 'w')
    json.dump(planning_result, f_p)

    # Save total fibers and ducts to be used as brownfield for further scenarios
    total_fiber = os.path.join(output_fds, 'Total_fiber_{0}'.format(output_name))
    check_exists(total_fiber)

    if not ff_protection:
        arcpy.Merge_management([lmf, df, ff], total_fiber)
    else:
        arcpy.Merge_management([lmf, df, ff, ff_p], total_fiber)

    total_duct = os.path.join(output_fds, 'Total_duct_{0}'.format(output_name))
    check_exists(total_duct)
    arcpy.Dissolve_management(total_fiber, total_duct)

    return


########################################################################################################################
if __name__ == '__main__':

    from_pycharm = False

    if not from_pycharm:
        network_nd_in = arcpy.GetParameterAsText(0)

        clustering_allocation_in = bool(arcpy.GetParameterAsText(1))

        ff_protection_in = bool(arcpy.GetParameterAsText(2))
        sp_protection_in = bool(arcpy.GetParameterAsText(3))

        sr_rn1_in = int(arcpy.GetParameterAsText(4))
        sr_rn2_in = int(arcpy.GetParameterAsText(5))

        buildings_in = arcpy.GetParameterAsText(6)

        joint_planning_in = bool(arcpy.GetParameterAsText(7))
        bs_in = arcpy.GetParameterAsText(8)

        sc_in = arcpy.GetParameterAsText(9)
        sc_wdm_in = bool(arcpy.GetParameterAsText(10))

        intersections_in = arcpy.GetParameterAsText(11)
        arcpy.AddMessage(intersections_in)
        co_in = arcpy.GetParameterAsText(12)

        save_lmf_df_in = bool(arcpy.GetParameterAsText(13))
        save_clusters_in = bool(arcpy.GetParameterAsText(14))

        brownfield_duct_in = arcpy.GetParameterAsText(15)
        if not brownfield_duct_in:
            brownfield_duct_in = '#'

        output_dir_in = arcpy.GetParameterAsText(16)  # r'D:\GISworkspace\ITSplanning' #
        output_fds_in = arcpy.GetParameterAsText(17)
        output_name_in = arcpy.GetParameterAsText(18)  # 'test' #

    else:
        network_nd_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun\Ottobrun_ND'

        clustering_allocation_in = True

        ff_protection_in = True
        sp_protection_in = True

        joint_planning_in = False
        bs_in = r''

        sc_in = r''
        sc_wdm_in = False

        buildings_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun\BSs_pushed'

        intersections_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun\Ottobrun_ND_Junctions'
        co_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun\CO_Ottobrun'

        sr_rn1_in = 16
        sr_rn2_in = 4

        brownfield_duct_in = r''

        output_dir_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018'
        output_fds_in = r'D:\GISworkspace\3_Demos\2_IndustryDay13072018\Topologies.gdb\Ottobrun_hpon'
        output_name_in = 'test_hpon'



#network_nd, clustering_allocation, ff_protection, sp_protection, buildings, intersections, co, sr_rn1, sr_rn2,
#         output_dir, output_fds, output_name, joint_planning=False, bs='#', sc='#', sc_wdm='#', save_lmf_df=False,
 #        save_clusters=False

    main(network_nd_in, clustering_allocation_in, ff_protection_in, sp_protection_in, buildings_in, intersections_in,
         co_in, sr_rn1_in, sr_rn2_in, output_dir_in, output_fds_in, output_name_in, joint_planning_in, bs_in, sc_in,
         sc_wdm_in, brownfield_duct_in, save_lmf_df_in, save_clusters_in)