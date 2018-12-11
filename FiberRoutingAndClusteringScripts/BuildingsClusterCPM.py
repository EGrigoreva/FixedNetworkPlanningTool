import arcpy
import os
import math
import time

# Check out the Network Analyst extension license
arcpy.CheckOutExtension("Network")


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
    """
    
    :param layer_in: 
    :return: 
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


def penalty_update(numb_in, thr_in, cost_matrix, keys, count_in=0):
    """
    
    :param numb_in: 
    :param thr_in: 
    :param cost_matrix: 
    :param keys: 
    :param count_in: 
    :return: 
    """
    penalty = {}  # empty penalty dictionary
    length = len(cost_matrix.keys())  # Number of entries in cost matrix

    if count_in != 0:
        ids_range = count_in + 1
    else:
        ids_range = numb_in + 1

    # Construct penalty dictionary
    for h in range(1, ids_range):

            # index to iterate through cost, as we need not all the entries, we make a custom iteration
            g = numb_in * (h - 1) + 1
            if g < length:
                penalty[h] = {}
                penalty[h]['max_cost'] = 0
                penalty[h]['accum_cost'] = 0
                # Calculate accumulated cost = sum of indiv. total lengths
                n = 0
                while n < thr_in:
                    if g <= length:
                        penalty[h]['accum_cost'] += cost_matrix[g][keys[4]]
                        if penalty[h]['max_cost'] < cost_matrix[g][keys[4]]:
                            penalty[h]['max_cost'] = cost_matrix[g][keys[4]]
                        n += 1
                    if g < length:
                        g += 1
                        if g > numb_in * (h - 1) + numb_in:
                            break
                    elif count_in != 0 and g >= length:
                        break

    # Sort penalty matrix
    acc_list = []  # List for total (accumulated cost)
    max_list = []  # Maximum cost (length)

    # Make a sortable structure out of a penalty dict.
    for key_i in penalty.keys():  # for all the base stations
        acc_list.append((key_i, penalty[key_i]['accum_cost']))
        max_list.append((key_i, penalty[key_i]['max_cost']))

    # Sort the values by accumulated length, accending
    sort_in = sorted(acc_list, key=lambda x: x[1])
    # sort_in = sorted(max_list, key=lambda x: x[1])

    return sort_in


# Convert an attribute table into python dictionary
# http://gis.stackexchange.com/questions/54804/fastest-methods-for-modifying-attribute-tables-with-python
def make_attribute_dict(fc, key_field, attr_list=['*']):
    """
    
    :param fc: 
    :param key_field: 
    :param attr_list: 
    :return: 
    """

    attdict = {}

    # define an empty dictionary
    fc_field_objects = arcpy.ListFields(fc)
    fc_fields = [field.name for field in fc_field_objects if field.type != 'Geometry']

    # checking input parameters
    if attr_list == ['*']:
        valid_fields = fc_fields
    else:
        valid_fields = [field for field in attr_list if field in fc_fields]

    # Ensure that key_field is always the first field in the field list
    cursor_fields = [key_field] + list(set(valid_fields) - set([key_field]))

    # step through the table
    with arcpy.da.SearchCursor(fc, cursor_fields) as cursor:
        for row in cursor:
            attdict[row[0]] = dict(zip(cursor.fields, row))
    return attdict


def main(nd, nodes, sr, intersections, output_dir_fc, pro, name_clst):

    n_nodes = int(arcpy.GetCount_management(nodes).getOutput(0))
    n_clusters = int(math.ceil(float(n_nodes) / float(sr)))

    ###########################################################################################################
    # Get the cost matrix: OD
    ###########################################################################################################

    # Set local variables
    layer_name = "ODcostMatrix"
    impedance = "Length"

    layer_path = os.path.join('in_memory', 'od_layer')
    check_exists(layer_path)

    # Create and get the layer object from the result object. The OD cost matrix layer can
    # now be referenced using the layer object.
    layer_object = arcpy.na.MakeODCostMatrixLayer(nd, layer_path, impedance).getOutput(0)

    # Get the names of all the sublayers within the OD cost matrix layer.
    sublayer_names = arcpy.na.GetNAClassNames(layer_object)

    # Stores the layer names that we will use later
    origins_layer_name = sublayer_names["Origins"]
    destinations_layer_name = sublayer_names["Destinations"]
    lines_layer_name = sublayer_names["ODLines"]

    # Load the intersections as both origin and destinations.
    arcpy.na.AddLocations(layer_object, origins_layer_name, nodes)
    arcpy.na.AddLocations(layer_object, destinations_layer_name, nodes)

    # Solve the OD cost matrix layer
    arcpy.na.Solve(layer_object)

    # Get the Lines Sublayer (all the distances)
    if not pro:
        lines_sublayer = arcpy.mapping.ListLayers(layer_object, lines_layer_name)[0]

    else:
        lines_sublayer = layer_object.listLayers(lines_layer_name)[0]

    lines = os.path.join('in_memory', lines_layer_name)

    arcpy.management.CopyFeatures(lines_sublayer, lines)

    ################################################################################################################
    # Gathering the data for the penalty matrix
    ################################################################################################################
    leng = int(arcpy.GetCount_management(lines_sublayer).getOutput(0))  # Number of paths from every BS to every intersection

    if sr < n_nodes:
        thr = int(sr)
    else:
        thr = int(n_nodes)

    # Make the # of clusters more to avoid the splitting of the clusters
    if thr != int(n_nodes):
        n_clusters_tmp = int(math.ceil(float(n_nodes) / float(sr)))
        n_clusters = n_clusters_tmp + int(math.ceil(float(n_clusters_tmp)/2))
        arcpy.AddMessage(n_clusters)
        thr = int(math.ceil(float(n_nodes)/float(n_clusters)))

    # Convert  attribute table of lines from optimization to python nested dict
    cost = make_attribute_dict(lines, "ObjectID", ["OriginID", 'DestinationID', 'DestinationRank', 'Total_Length'])
    cost_keys = ["ObjectID", "OriginID", 'DestinationID', 'DestinationRank', 'Total_Length']

    node_id_field = get_ids(nodes)
    nodes_dict = make_attribute_dict(nodes, node_id_field)

    ################################################################################################################
    # Clustering
    ################################################################################################################

    # Define a list of non-available nodes for clustering
    flags = set()
    # Define clustering dictionary
    clustering = {}

    count = n_nodes
    index = 0

    j = 1  # iterator through the cost matrix
    cl = 1  # counter fr the cluster

    sort = penalty_update(n_nodes, thr, cost, cost_keys, index)  # calculate penalty matrix
    cost_len = len(nodes_dict)

    for i in range(0, count):  # for all the nodes
        k = 0  # counter for number of cluster members
        if j <= leng:
            if len(flags) != n_nodes:
                node = sort[i][0]
                if node not in flags:
                    clustering[cl] = {}
                    clustering[cl]['members'] = []
                    # We need to traverse the cost matrix. However we start not from the first element. As the matrix
                    # structure is regular we can calculate the starting index for our array to assign the (X,Y)
                    # to the seed master. E.g., we have three elements [1, 2, 3] then we have 111222333 structure, where
                    # 3 starts from position 7 number of nodes is 3, thus 3*(3-1)+1 = 7. for 1 it is 3*(1-1)+1 = 1 and
                    # for 2 is 3*(2-1)+1 = 4
                    j = cost_len * (node - 1) + 1

                    while k < thr:
                        # now we need to populate the cluster dict with non-clustered yet members
                        if cost[j][cost_keys[2]] not in flags:
                            member_id = cost[j][cost_keys[2]]
                            clustering[cl]['members'].append((member_id,  j))
                            flags.add(member_id)
                            k += 1
                            if j < leng:
                                j += 1
                            else:
                                break
                        else:
                            if j < leng:
                                j += 1
                                if len(flags) == n_nodes:
                                    break
                    cl += 1

        else:
            break

    # print(clustering)

    # By select by attribute select all the cluster members
    nodes_layer = os.path.join('in_memory', 'nodes')
    check_exists(nodes_layer)
    arcpy.MakeFeatureLayer_management(nodes, nodes_layer)

    int_layer = os.path.join('in_memory', 'int_layer')
    check_exists(int_layer)
    arcpy.MakeFeatureLayer_management(intersections, int_layer)

    int_id_field = get_ids(intersections)

    cluster_heads = []

    for i in range(0, n_clusters):
        n_members = len(clustering[i+1]['members'])
        # print('***********************************************************')
        # print('Cluster # {0}'.format(i))
        # print('# Members {0}'.format(n_members))

        for j in range(0, n_members):
            # print('Iterating through member # {0}'.format(j))
            if j == 0:
                clause_nodes = '{0} = {1}'.format(node_id_field, clustering[i+1]['members'][j][0])

            elif j > 0:
                clause_nodes += ' OR {0} = {1}'.format(node_id_field, clustering[i+1]['members'][j][0])

        # print(clause_nodes)
        arcpy.SelectLayerByAttribute_management(nodes_layer, selection_type='NEW_SELECTION', where_clause=clause_nodes)

        name_cluster = 'Cluster_{0}_{1}'.format(i, name_clst)
        out_cluster = os.path.join(output_dir_fc, name_cluster)
        check_exists(out_cluster)
        arcpy.CopyFeatures_management(nodes_layer, out_cluster)

        # Find the centroid of the cluster
        out_cluster_head_tmp = os.path.join('in_memory', 'cluster_head_tmp')
        check_exists(out_cluster_head_tmp)
        arcpy.MeanCenter_stats(out_cluster, out_cluster_head_tmp)

        # Find the closest intersection to the centroid
        arcpy.Near_analysis(out_cluster_head_tmp, intersections, method='GEODESIC')

        with arcpy.da.SearchCursor(out_cluster_head_tmp, 'NEAR_FID') as cursor:
            for row in cursor:
                intersection_id = row[0]

        clause_int = '{0} = {1}'.format(int_id_field, intersection_id)
        arcpy.SelectLayerByAttribute_management(int_layer, selection_type='NEW_SELECTION', where_clause=clause_int)

        name_cluster_head = 'Cluster_head_{0}_{1}'.format(i, name_clst)
        # print(name_cluster_head)
        out_cluster_head = os.path.join(output_dir_fc, name_cluster_head)
        check_exists(out_cluster_head)
        arcpy.CopyFeatures_management(int_layer, out_cluster_head)
        cluster_heads.append(out_cluster_head)

    # Merge clusterheads
    merge_name = os.path.join('in_memory', 'Merged_cluster_heads_sr{0}'.format(sr))
    check_exists(merge_name)
    arcpy.Merge_management(cluster_heads, merge_name)

    # Save them to a file
    name_cluster_heads = os.path.join(output_dir_fc,  'Cluster_heads_{0}'.format(name_clst))
    check_exists(name_cluster_heads)
    arcpy.CopyFeatures_management(merge_name, name_cluster_heads)

    return n_clusters


if __name__ == '__main__':

    nd_in = r'D:\GISworkspace\1_Papers\AbstractTopologies\TestSmall.gdb\Geo_URBAN_Munich\Geo_URBAN_Munich_ND_medium'

    nodes_in = r'D:\GISworkspace\1_Papers\AbstractTopologies\TestSmall.gdb\Geo_URBAN_Munich\Munich_buildings_medium'
    intersections_in = r'D:\GISworkspace\1_Papers\AbstractTopologies\TestSmall.gdb\Geo_URBAN_Munich\Munich_intersections_medium'
    output_dir_fc_in = r'D:\GISworkspace\1_Papers\AbstractTopologies\TestSmall.gdb\Results_medium'

    sr_in = 32

    pro_in = True

    start_time = time.time()

    # nd, nodes, sr, intersections, output_dir_fc, pro
    main(nd_in, nodes_in, sr_in, intersections_in, output_dir_fc_in, pro_in)

    end_time = time.time() - start_time
    print(end_time)
