import numpy as np
import scipy.sparse as sps
import porepy as pp

"""

Acknowledgements:
    The functionalities related to the edge computations are modified from
    github.com/anabudisa/md_aux_precond developed by Ana Budisa and Wietse M. Boon.
"""

def compute_edges(grid):
    if isinstance(grid, pp.Grid):
        if grid.dim == 3:
            _compute_edges_3d(grid)
        elif grid.dim == 2:
            _compute_edges_2d(grid)
        elif grid.dim == 1:
            _compute_edges_1d(grid)
        elif grid.dim == 0:
            _compute_edges_0d(grid)

    if isinstance(grid, pp.GridBucket):
        for g, _ in grid:
            compute_edges(g)

def _compute_edges_0d(g):
    g.edge_nodes = sps.csc_matrix((1, 1), dtype=np.int)
    g.face_edges = sps.csc_matrix((1, 1), dtype=np.int)

def _compute_edges_1d(g):
    g.edge_nodes = sps.csc_matrix((g.num_nodes, 1), dtype=np.int)
    g.face_edges = sps.csc_matrix((1, g.num_faces), dtype=np.int)

def _compute_edges_2d(g):
    # Edges in 2D are nodes

    R = pp.map_geometry.project_plane_matrix(g.nodes)
    rot = np.dot(R.T, np.dot(np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]]), R))
    face_tangential = rot.dot(g.face_normals)

    face_edges = g.face_nodes.copy().astype(np.int)

    nodes = sps.find(g.face_nodes)[0]
    for face in np.arange(g.num_faces):
        loc = slice(g.face_nodes.indptr[face], g.face_nodes.indptr[face + 1])
        nodes_loc = np.sort(nodes[loc])

        tangent = g.nodes[:, nodes_loc[1]] - g.nodes[:, nodes_loc[0]]
        sign = np.sign(np.dot(face_tangential[:, face], tangent))

        face_edges.data[loc] = [-sign, sign]

    g.edge_nodes = sps.csc_matrix(np.ones((1, g.num_nodes), dtype=np.int))
    g.face_edges = face_edges

def _compute_edges_3d(g):
    # Number of edges per face, assumed to be constant.
    n_e = g.face_nodes[:,0].nnz

    # Pre-allocation
    edges = np.ndarray((2, n_e*g.num_faces), dtype=np.int)

    for face in np.arange(g.num_faces):
        # find indices for nodes of this face
        loc = g.face_nodes.indices[g.face_nodes.indptr[face]:\
                                   g.face_nodes.indptr[face + 1]]
        # Define edges between each pair of nodes
        # assuming ordering in face_nodes is done
        # according to right-hand rule
        edges[:, n_e*face:n_e*(face+1)] = np.row_stack((loc, np.roll(loc, -1)))

    # Save orientation of each edge w.r.t. the face
    orientations = np.sign(edges[1,:] - edges[0,:])

    # Edges are oriented from low to high node indices
    edges.sort(axis=0)
    edges, _, indices = pp.utils.setmembership.unique_columns_tol(edges)

    # Generate edge-node connectivity such that
    # edge_nodes(i, j) = +/- 1:
    # edge j points to/away from node i
    indptr = np.arange(0, edges.size + 1, 2)
    ind = np.ravel(edges, order="F")
    data = -(-1)**np.arange(edges.size)
    g.edge_nodes = sps.csc_matrix((data, ind, indptr))

    # Generate face_edges such that
    # face_edges(i, j) = +/- 1:
    # face j has edge i with same/opposite orientation
    # with the orientation defined according to the right-hand rule
    indptr = np.arange(0, indices.size + 1, n_e)
    g.face_edges = sps.csc_matrix((orientations, indices, indptr))
