####################################################################
######## Event display code for vertices ###########################
######## Contact for comments to wasikul.islam@cern.ch #############
####################################################################

import uproot
import matplotlib.pyplot as plt
import numpy as np
import math
from math import log, tan, cosh, sqrt, pi
from matplotlib.lines import Line2D  # Explicit import of Line2D
import awkward as ak
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import argparse
import mplhep as mh

mh.style.use("ATLAS")
# Other mplhep styles available, if you'd rather use one of these instead:
#mh.style.use("CMS")
#mh.style.use("ALICE")
#mh.style.use("LHCb")
#mh.style.use("ROOT")

root_file = uproot.open('sample.root')

tree = root_file["ntuple"]

my_branches = tree.arrays(['TruthVtx_z', 'TruthVtx_isHS','RecoVtx_isHS', 'Track_truthVtx_idx', 'TruthVtx_isHS', 'RecoVtx_isPU', 'RecoVtx_sumPt2', 'RecoVtx_track_idx', 'AntiKt4EMTopoJets_track_idx', 'RecoVtx_z', 'Track_z0', 'Track_qOverP', 'Track_theta', 'Track_phi', 'Track_var_z0', 'AntiKt4EMTopoJets_pt', 'AntiKt4EMTopoJets_eta', 'AntiKt4EMTopoJets_phi', 'AntiKt4EMTopoJets_truthHSJet_idx',
                            'RecoVtx_x', 'RecoVtx_y', 'RecoVtx_track_weight', 'Track_time', 'Track_timeRes',
                            'Track_hasValidTime', 'TruthVtx_x', 'TruthVtx_y', 'averageInteractionsPerCrossing'])

#############################################################
parser = argparse.ArgumentParser(description='Process event and vertex data from ROOT file.')
parser.add_argument('--event_num', type=int, required=True, help='Event number to process')
parser.add_argument('--vtxID', type=int, required=True, help='Vertex ID to process')
args = parser.parse_args()

event_num = args.event_num
vtxID = args.vtxID

#############################################################

vtx_z = my_branches.RecoVtx_z[event_num][vtxID]
sumpt = my_branches.RecoVtx_sumPt2[event_num][vtxID]
truth_z = my_branches.TruthVtx_z[event_num][0]

selected_HS_vtx_id = None
max_sumpt = float('-inf')
my_track_z0=[]

max_sumpt_all = -1.0          # track max over *all* vertices
selected_all_vtx_id = -1      # index of overall max


# Iterate through the vertex z-values and sumpt values
for idx, z in enumerate(my_branches.RecoVtx_z[event_num]):
    sumpt_value = my_branches.RecoVtx_sumPt2[event_num][idx]

    # --- overall maximum (no condition) ---
    if sumpt_value > max_sumpt_all:
        max_sumpt_all = sumpt_value
        selected_all_vtx_id = idx
    #print("reco vertex within 5 mm of truth z : ", z, "vtx id:", idx, "sumpt :", sumpt_value, "|(z - truth_z)| :", abs(z - truth_z))
    if abs(z - truth_z) <= 10:
        print("reco vertex within 5 mm of truth z : ", z, "vtx id:", idx, "sumpt :", sumpt_value, "|(z - truth_z)| :", abs(z - truth_z))
        if  sumpt_value > max_sumpt:
            selected_HS_vtx_id = idx
            max_sumpt = my_branches.RecoVtx_sumPt2[event_num][idx]
            
print(f"python event_display_VBF_R25.py --event_num {event_num} --vtxID {selected_HS_vtx_id}")
print("selected_all_vtx_id", selected_all_vtx_id, "selected_HS_vtx_id within 10 mm:", selected_HS_vtx_id)


# Print the selected vertex and its sumpt value
if selected_HS_vtx_id is not None:
    print("Evt# ", event_num, f" Selected Vertex ID: {selected_HS_vtx_id}")
    #print(f"Sumpt of Selected Vertex: {max_sumpt}")
else:
    print("No vertices found within the specified range.")

if (vtxID == selected_HS_vtx_id):
    print("This is HS vertex")
else :
    print("This is PU vertex")

# Get the vertex z-coordinate
print("isHS =",my_branches.RecoVtx_isHS[event_num][vtxID] , " isPU =",my_branches.RecoVtx_isPU[event_num][vtxID])


closest_vertices = []
reco_vertices = []
for idx, z in enumerate(my_branches.RecoVtx_z[event_num]):
    if abs(z - vtx_z) <= 5:
        reco_vertices.append((z, idx))
        diff = abs(z - vtx_z)
        closest_vertices.append((idx, z, diff))

closest_vertices.sort(key=lambda x: x[2])
# Display the closest vertices
for idx, z, diff in closest_vertices:
    #print(f"Vertex ID: {idx}, Z: {z}, Difference from vtx_z: {diff}")
    if (idx==selected_HS_vtx_id):
        print("closest HS vertex# :", idx)
    
truth_vertices = []
for idx, z in enumerate(my_branches.TruthVtx_z[event_num]):
    if abs(z - vtx_z) <= 5:
        truth_vertices.append((z, idx))
        
#####################################################

# Get the tracks connected to the selected vertex
connected_tracks = my_branches.RecoVtx_track_idx[event_num][vtxID]
#print("no. of tracks:", len(my_branches.RecoVtx_track_idx[event_num][vtxID]))

track_info = []
jet_info = []
num_jets = 0
new_sumpt=0
num_HS_tracks=0

# -------------------------------
# Process tracks of Primary vertex
# -------------------------------

for idx in connected_tracks:
    track_z0 = my_branches.Track_z0[event_num][idx]
    p = abs(1 / (my_branches.Track_qOverP[event_num][idx]))
    track_eta = -np.log(math.tan((my_branches.Track_theta[event_num][idx]) / 2))
    track_pT = (p / (np.cosh(track_eta))) / 1000
    track_phi = my_branches.Track_phi[event_num][idx]
    z0 = track_z0 - vtx_z

    print("######## track_pT: ", track_pT, "GeV || track_eta:", track_eta, "##########")
    
    ################################
    #if (track_pT>25):
    #    continue
    ################################
    
    my_track_z0.append(track_z0)

    ####################################################
    ### Associate jets to this vertex by Rpt ###########
    ####################################################

    # Loop over jets
    for j in range(len(my_branches.AntiKt4EMTopoJets_track_idx[event_num])):
        if my_branches.AntiKt4EMTopoJets_pt[event_num][j] < 30.0: #default is 30.0 GeV
            continue

        trackPT = 0
        for q in range(len(my_branches.AntiKt4EMTopoJets_track_idx[event_num][j])):
            # Track selection cuts
            jdx = my_branches.AntiKt4EMTopoJets_track_idx[event_num][j][q]
            p2 = abs(1 / my_branches.Track_qOverP[event_num][jdx])
            eta2 = -log(tan(my_branches.Track_theta[event_num][jdx] / 2))
            track_pT2 = p2 / cosh(eta2)
            pt2 = track_pT2 / 1000

            delz = my_branches.Track_z0[event_num][jdx] - my_branches.RecoVtx_z[event_num][vtxID]
            signi_cut = delz / sqrt(my_branches.Track_var_z0[event_num][jdx])

            if abs(signi_cut) > 3.0:
                continue
            trackPT += pt2

        Rpt = trackPT / my_branches.AntiKt4EMTopoJets_pt[event_num][j]
        #print("jet#", j, "jet_pt", my_branches.AntiKt4EMTopoJets_pt[event_num][j], "Rpt:", Rpt)

        jet_pt = my_branches.AntiKt4EMTopoJets_pt[event_num][j]
        jet_eta = my_branches.AntiKt4EMTopoJets_eta[event_num][j]
        jet_phi = my_branches.AntiKt4EMTopoJets_phi[event_num][j]
        jet_isHS = my_branches.AntiKt4EMTopoJets_truthHSJet_idx[event_num][j]
        jet_isHS_size = len(jet_isHS)
        jet_pz = jet_pt * np.sinh(jet_eta)

        jet_signX = np.sign(jet_eta) if jet_eta != 0 else 1  # Avoid division by zero
        jet_signY = np.sign(np.sin(jet_phi)) if np.sin(jet_phi) != 0 else 1

        jet_theta = np.arctan(jet_pt / abs(jet_pz))
        jet_x = (jet_pt / 40) * np.cos(jet_theta) * jet_signX
        jet_y = (jet_pt / 40) * np.sin(jet_theta) * jet_signY
        #print("Jet : ", " pt :", jet_pt, "eta :", jet_eta, "isHS :", jet_isHS_size)

        jet_tuple = (jet_pt, jet_eta, jet_phi, jet_isHS_size, jet_x, jet_y, Rpt)

        if jet_tuple not in jet_info:
            jet_info.append(jet_tuple)

        #num_jets += 1  # Increment counter

        if Rpt < 0.02:
        #if Rpt < 0.00:
            continue

    ####################################################
    ####################################################


    new_sumpt= new_sumpt + (track_pT ** 2)

    pz = track_pT * math.sinh(track_eta)
    signX = track_eta / abs(track_eta)
    signY = math.sin(track_phi) / abs(math.sin(track_phi))
    theta = math.atan(track_pT / abs(pz))
    x = (track_pT / 2) * math.cos(theta) * signX
    y = (track_pT / 2) * math.sin(theta) * signY

    #status = my_branches.track_status[event_num][idx]
    #status = my_branches.Track_isTruthHS[event_num][idx]
    Track_truthVtx_id = my_branches.Track_truthVtx_idx[event_num][idx]
    if (Track_truthVtx_id==-1):
        continue

    status = my_branches.TruthVtx_isHS[event_num][Track_truthVtx_id]
    
    if (status==1):
        num_HS_tracks=num_HS_tracks+1
    
    track_info.append([vtx_z, z0, x, y, status])
    #track_info.append(compute_track_line(track_pT, track_eta, track_phi, vtx_z, z0, status))

print("number of HS tracks : ", num_HS_tracks)

# Plot the graph
plt.figure(figsize=(12, 6))


################### Draw Tracks ###############################
secondary_tracks = [trk for trk in track_info if trk[4] == 100]
primary_tracks   = [trk for trk in track_info if trk[4] != 100]

for track in primary_tracks:
    Z = track[0]
    z0 = track[1]
    x = track[2]
    y = track[3]
    status = track[4]
    if status == 1:
        color = 'blue'  # Set color to blue for hard-scatter tracks
    elif status == 0:
        color = 'red'
    elif status == 2:        
        color = 'green'
    elif status == 3:        
        color = 'cyan' 
    else:
        color = 'black' 
    plt.plot([Z + z0, Z + z0 + x], [0, y], color=color)

#for track in secondary_tracks:
#    z, z0, dx, dy, _ = track
#    plt.plot([z, z + dx], [0, dy], color='brown', linestyle='--')   # Secondary
    
################## Draw Reference eta lines ##################################
def draw_eta_reference_lines(vtx_z, eta_ref, line_length=50, linestyle='dashed'):
    theta_ref_pos = 2 * np.arctan(np.exp(-eta_ref))  # For +eta_ref
    theta_ref_neg = 2 * np.arctan(np.exp(eta_ref))   # For -eta_ref (neg. eta)

    # Compute x and y components based on theta
    x_ref_pos = line_length * np.cos(theta_ref_pos)
    y_ref_pos = line_length * np.sin(theta_ref_pos)

    x_ref_neg = line_length * np.cos(theta_ref_neg)
    y_ref_neg = -line_length * np.sin(theta_ref_neg)  # Negative y for -eta_ref

    # Compute mirrored lines
    y_ref_pos_mirror = -y_ref_pos
    y_ref_neg_mirror = -y_ref_neg

    # Draw the reference lines
    plt.plot([vtx_z, vtx_z + x_ref_pos], [0, y_ref_pos], linestyle=linestyle, color='lightgrey')
    plt.plot([vtx_z, vtx_z + x_ref_neg], [0, y_ref_neg], linestyle=linestyle, color='lightgrey')
    plt.plot([vtx_z, vtx_z + x_ref_pos], [0, y_ref_pos_mirror], linestyle=linestyle, color='lightgrey')
    plt.plot([vtx_z, vtx_z + x_ref_neg], [0, y_ref_neg_mirror], linestyle=linestyle, color='lightgrey')
    
    # Define label position
    label_x_eta = vtx_z + 3.5
    label_y_eta = 0.05

    # Adjust y position for multiple labels to avoid overlap
    offset = 0.05 * (eta_ref - 2.5)  # Slight shift based on eta_ref value
    plt.plot([label_x_eta - 0.4, label_x_eta], [label_y_eta - 0.90 - offset, label_y_eta - 0.90 - offset], linestyle=linestyle, color='lightgrey', linewidth=1.5)
    plt.text(label_x_eta + 0.2, label_y_eta - 0.90 - offset, fr'$\eta = {eta_ref}$', fontsize=12, color='lightgrey')

linestyles = ['dashed', 'dotted']
for i, eta in enumerate([2.5, 4.0]):
    draw_eta_reference_lines(vtx_z, eta_ref=eta, linestyle=linestyles[i])


################## Draw Jets ##################################
text_index = 0

for i in range(len(jet_info)):
    x_jet = jet_info[i][4]  # jet_x is at index 4
    y_jet = jet_info[i][5]  # jet_y is at index 5
    isHS = jet_info[i][3]
    Rpt = jet_info[i][6]
    
    #print("jet#", i, "jet_pt:", jet_info[i][0], "isHS:", isHS, "Rpt:", Rpt)

    
    # Condition to filter jets
    if num_HS_tracks > 0 and abs(vtx_z - truth_z) < 2:
        if isHS == 0:
            continue  # Skip non-HS jets when this condition is met
    else:
        if isHS == 0 and Rpt < 0.02:
            continue

    color = 'green' if isHS >= 1 else 'grey'
    alpha = 1.0
    
    cone_length = np.sqrt(x_jet**2 + y_jet**2)  # Length of the cone
    cone_width = cone_length * 0.3  # Width proportional to length

    # Perpendicular vector for cone base width
    norm = np.sqrt(x_jet**2 + y_jet**2)
    perp_x = -y_jet / norm * cone_width / 2
    perp_y = x_jet / norm * cone_width / 2

    # Define cone vertices (triangle)
    tip_x, tip_y = vtx_z, 0  # Tip at the vertex z location
    base_left_x, base_left_y = vtx_z + x_jet + perp_x, y_jet + perp_y
    base_right_x, base_right_y = vtx_z + x_jet - perp_x, y_jet - perp_y

    plt.fill([tip_x, base_left_x, base_right_x], [tip_y, base_left_y, base_right_y], color=color, alpha=0.5)
    jet_text = f"Jet {text_index+1}: $p_T$={jet_info[i][0]:.0f} GeV, $\eta$={jet_info[i][1] :.1f}"
    color2 = 'green' if isHS >= 1 else 'black'  # Set color based on isHS value
    #plt.text(vtx_z - 4.5 - 0.35, 0.9 - (1.2 + text_index * 0.1), jet_text, weight='bold', fontsize=12, color=color2)
    plt.text(vtx_z - 4.5 - 0.35, 1.05 - (1.2 + text_index * 0.1), jet_text, weight='bold', fontsize=12, color=color2)
    text_index += 1
################################################################
    
# Determine the x-coordinate based on the Z coordinate range
x_coord = vtx_z-4.8  # Set it to the minimum x-coordinate of the line_positions
y_coord = 0.9  # Set the y-coordinate for the text annotations
plt.text(x_coord, y_coord, f"Reco z = {vtx_z:.1f} mm", weight='bold', fontsize=12)
plt.text(x_coord, y_coord - 0.1, f"Truth z = {truth_z:.1f} mm", weight='bold', fontsize=12)

m1, e1 = f"{new_sumpt:.1e}".split("e")
e1 = int(e1)

plt.text(
    x_coord, y_coord - 0.2,
    rf"$\sum \mathbf{{p_T^2}}$ = $\mathbf{{{m1}\times 10^{{{e1}}}\ \mathbf{{GeV^2}}}}$",
    weight='bold', fontsize=12
)

################## Add tracks and jets legend ###################

track_legend = [mlines.Line2D([], [], color='blue', label='HS tracks'),
                mlines.Line2D([], [], color='red', label='PU tracks')] #, 
                #mlines.Line2D([], [], color='brown', label='Secondary Tracks', linestyle='--')]

jet_legend = [mpatches.Rectangle((0, 0), 1, 1,  color='green', alpha=0.5, label='HS jet'),
              mpatches.Rectangle((0, 0), 1, 1,  color='grey', alpha=0.5, label='PU jet')]

# Combine both legends into one
hs_legend = plt.legend(handles=track_legend + jet_legend, loc='upper right', title='Track and Jet Types', bbox_to_anchor=(1.0, 0.85), fontsize=11, title_fontsize=12)

# Add the legend manually to the plot
plt.gca().add_artist(hs_legend)

##################### Draw Reco and truth vertices ###############

# Plot the line for the recovertex_z values
reco_vertices_z = [z for z, _ in reco_vertices]
marker_colors_reco = ['blue' if z == vtx_z else 'black' for z in reco_vertices_z]
plt.scatter(reco_vertices_z, [0] * len(reco_vertices_z), color=marker_colors_reco, marker='o', s=100)
plt.axhline(y=0.0, color='black', linestyle='--')

truth_vertices_z = [z for z, _ in truth_vertices]
marker_colors = ['blue' if z == truth_z else 'black' for z in truth_vertices_z]
plt.scatter(truth_vertices_z, [-0.75] * len(truth_vertices_z), color=marker_colors, marker='|', s=100)
plt.axhline(y=-0.75, color='black', linestyle='--')

label_x = vtx_z + 3.5
label_y = 0.05
plt.text(label_x, label_y-0.15, 'Reco vertices', fontsize=12)
plt.text(label_x, label_y-0.75, 'Truth vertices', fontsize=12)
#plt.text(label_x-3, 0.85, 'ATLAS Simulation Preliminary', fontsize=16, weight='bold', style='italic')
#plt.text(label_x-2.2, 0.85, 'ATLAS Simulation Internal', fontsize=16, weight='bold', style='italic')
#plt.text(label_x-2.2, 0.85, r'$\mathbf{ATLAS}$ Simulation Internal', fontsize=16)

ax = plt.gca()
#ax.text(0.68, 0.96, "ATLAS",transform=ax.transAxes,fontsize=16,fontweight='bold',va='top', ha='left')
#ax.text(0.76, 0.96, "Simulation Internal",transform=ax.transAxes,fontsize=16,va='top', ha='left')
#ax.text(0.68, 0.90, r'$\sqrt{s}=14$ TeV, $\langle\mu\rangle=200$, $t\bar{t}$', transform=ax.transAxes, fontsize=13,va='top', ha='left')

ax.text(0.79, 0.96, r'$\sqrt{s}=14$ TeV, $\langle\mu\rangle=200$, $t\bar{t}$', transform=ax.transAxes, fontsize=13,va='top', ha='left')

#ax.text(0.38, 0.96, "ATLAS",transform=ax.transAxes,fontsize=16,fontweight='bold',va='top', ha='left')
#ax.text(0.46, 0.96, "Simulation Internal",transform=ax.transAxes,fontsize=16,va='top', ha='left')
#ax.text(0.33, 0.90, r'$\sqrt{s}=14$ TeV, $\langle\mu\rangle=200$, VBF $H\rightarrow$ Invisible', transform=ax.transAxes, fontsize=13,va='top', ha='left')


################################################################

plt.ylim(-1.0, 1.0)
plt.xlim(vtx_z-5.0, vtx_z+5.0)
#plt.title(f'Event# {event_num} : Vertex# {vtxID}')
plt.xlabel('Z [mm]')
#plt.ylabel('R [mm]')
plt.yticks([])
plt.legend()
plt.tight_layout()

#plt.grid(True)
plt.savefig(f'tt_fig_{event_num}_{vtxID}.png')



print(f"Event display has been saved as figures/fig_{event_num}_{vtxID}.png")

#plt.show()

##############################################################################
######## Full-event vertex-display suite (every reconstructed vertex  ########
######## in this event on one canvas) -- companion to the single-vertex ######
######## plot above, reusing the same --event_num / --vtxID CLI args and  ####
######## the same ntuple arrays already loaded into my_branches.        ######
##############################################################################
#
# Mirrors the plot suite event_display_all_vertices_VBF.py /
# event_display_all_vertices_VBF_3d.py produce for the VBF Rel21 sample
# (plain / sized+mu-annotated / time-coloured 2D views, a vertex-Z-vs-time
# scatter, and a genuinely 3D interactive Plotly page), adapted to this
# ntuple's own branch names (RecoVtx_*/Track_* instead of
# recovertex_*/track_*) and its per-track Track_time/Track_hasValidTime
# timing information (this ntuple has no direct track_status branch, so
# HS/PU is derived the same way the single-vertex plot above already does:
# via Track_truthVtx_idx -> TruthVtx_isHS). Output files use a "tt_" prefix
# so they never collide with the VBF script's fig_220_* outputs in the same
# figures/vertices/ directory.

import os
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import plotly
import plotly.graph_objects as go
import base64

AV_STATUS_COLOR = {1: 'blue', 0: 'red'}  # matches this file's own isHS convention


def build_all_vertex_tracks(evnum):
    """Loop over every reconstructed vertex/track in this event once,
    building everything needed for the plot suite below."""
    n_vtx_ev = len(my_branches.RecoVtx_z[evnum])
    all_tracks = []   # (vtx_z, dz0, x, y, status, time, has_time, weight)
    vtx_summary = []  # (vtx_z, sumpt2, is_HS, mean_time)

    for vid in range(n_vtx_ev):
        vz = float(my_branches.RecoVtx_z[evnum][vid])
        sumpt2 = float(my_branches.RecoVtx_sumPt2[evnum][vid])
        is_hs = bool(my_branches.RecoVtx_isHS[evnum][vid])

        conn = my_branches.RecoVtx_track_idx[evnum][vid]
        weights = my_branches.RecoVtx_track_weight[evnum][vid]

        vtx_times, vtx_weights = [], []
        for j, tidx in enumerate(conn):
            t_z0 = my_branches.Track_z0[evnum][tidx]
            p = abs(1.0 / my_branches.Track_qOverP[evnum][tidx])
            t_eta = -np.log(math.tan(my_branches.Track_theta[evnum][tidx] / 2))
            t_pt = (p / np.cosh(t_eta)) / 1000.0
            t_phi = my_branches.Track_phi[evnum][tidx]
            has_time = bool(my_branches.Track_hasValidTime[evnum][tidx])
            t_time = float(my_branches.Track_time[evnum][tidx]) if has_time else float('nan')
            w = float(weights[j]) if j < len(weights) else 1.0
            dz0 = t_z0 - vz

            truth_idx = my_branches.Track_truthVtx_idx[evnum][tidx]
            status = int(my_branches.TruthVtx_isHS[evnum][truth_idx]) if truth_idx != -1 else -1

            pz = t_pt * math.sinh(t_eta)
            signX = t_eta / abs(t_eta) if t_eta != 0 else 1
            signY = math.sin(t_phi) / abs(math.sin(t_phi)) if math.sin(t_phi) != 0 else 1
            th = math.atan(t_pt / abs(pz)) if pz != 0 else 0.0
            x = (t_pt / 2) * math.cos(th) * signX
            y = (t_pt / 2) * math.sin(th) * signY

            all_tracks.append((vz, dz0, x, y, status, t_time, has_time, w))
            if status == 0 and has_time:  # PU tracks only, timing is only meaningful there
                vtx_times.append(t_time)
                vtx_weights.append(w)

        mean_time = (np.average(vtx_times, weights=vtx_weights)
                     if len(vtx_times) > 0 else float('nan'))
        vtx_summary.append((vz, sumpt2, is_hs, mean_time))

    return all_tracks, vtx_summary


all_vtx_tracks, all_vtx_summary = build_all_vertex_tracks(event_num)
truth_vertices_z_full = [float(z) for z in my_branches.TruthVtx_z[event_num]]
mu_val = float(my_branches.averageInteractionsPerCrossing[event_num])
n_vtx_total = len(all_vtx_summary)

all_z = [v[0] for v in all_vtx_summary] + truth_vertices_z_full
z_min, z_max = min(all_z), max(all_z)
pad = 0.05 * (z_max - z_min)
av_overview_xlim = (z_min - pad, z_max + pad)

# Zoom centre: the same vertex selected on the command line (--vtxID),
# reused so the zoomed all-vertices view lines up with the single-vertex
# plot above.
av_zoom_center = vtx_z
av_zoom_xlim = (av_zoom_center - 5.0, av_zoom_center + 5.0)


def av_draw_tracks(ax, tracks):
    for (Z, dz0, x, y, status, time, has_time, w) in tracks:
        color = AV_STATUS_COLOR.get(status, 'black')
        ax.plot([Z + dz0, Z + dz0 + x], [0, y], color=color)


def av_draw_vertex_markers(ax, summary, sized=False):
    for (vz, sumpt2, is_hs, mean_time) in summary:
        size = 8 + 5.0 * math.sqrt(max(sumpt2, 0.0)) if sized else 5
        ax.plot([vz], [0], 'o', color='#444444' if sized else 'black',
                 markersize=size / 5 if sized else size, alpha=0.85, zorder=4)


def av_common_axes(ax, title):
    ax.axhline(y=0.0, color='black', linestyle='--', linewidth=0.8)
    ax.axhline(y=-0.75, color='black', linestyle='--', linewidth=0.8)
    ax.set_xlabel('Z [mm]')
    ax.set_ylabel('R [mm]')
    ax.set_ylim(-1, 1)
    ax.set_title(title)


def av_add_labels(ax, label_x):
    t1 = ax.text(label_x, 0.25, 'Reco vertices', fontsize=12)
    t2 = ax.text(label_x, -0.6, 'Truth vertices', fontsize=12)
    return [t1, t2]


def av_save_two_views(fig, ax, out_prefix):
    center = 0.5 * (av_overview_xlim[0] + av_overview_xlim[1])
    labels = av_add_labels(ax, center)
    ax.set_xlim(*av_overview_xlim)
    fig.savefig(f'{out_prefix}.png', dpi=150, bbox_inches='tight')
    for t in labels:
        t.remove()
    labels = av_add_labels(ax, av_zoom_center + 2.5)
    ax.set_xlim(*av_zoom_xlim)
    fig.savefig(f'{out_prefix}_zoomed_in.png', dpi=150, bbox_inches='tight')
    for t in labels:
        t.remove()


# =================================================================
# Version 0: plain style -- every reco/truth vertex and track in the event
# =================================================================
fig, ax = plt.subplots(figsize=(15, 5))
av_draw_tracks(ax, all_vtx_tracks)
av_draw_vertex_markers(ax, all_vtx_summary, sized=False)
ax.scatter(truth_vertices_z_full, [-0.75] * len(truth_vertices_z_full), color='black',
           marker='|', s=100, zorder=3)
hs_legend = ax.legend(handles=[mlines.Line2D([], [], color='blue', label='HS tracks'),
                                mlines.Line2D([], [], color='red', label='PU tracks')],
                       loc='upper right', title='Track Types', bbox_to_anchor=(0.3, 0.9))
ax.add_artist(hs_legend)
av_common_axes(ax, f"Event {event_num}: All Vertices and Tracks")
av_save_two_views(fig, ax, f'tt_fig_{event_num}_all_vertices')
plt.close(fig)

# =================================================================
# Version 1: "styled" -- vertices sized by sum(pT^2), pileup annotated
# =================================================================
fig, ax = plt.subplots(figsize=(15, 5.5))
ax.set_facecolor('#fbfbfb')
av_draw_tracks(ax, all_vtx_tracks)
av_draw_vertex_markers(ax, all_vtx_summary, sized=True)
ax.scatter(truth_vertices_z_full, [-0.75] * len(truth_vertices_z_full), color='black',
           marker='|', s=100, zorder=3)
hs_legend = ax.legend(
    handles=[mlines.Line2D([], [], color='blue', label='HS tracks'),
             mlines.Line2D([], [], color='red', label='PU tracks'),
             mlines.Line2D([], [], marker='o', color='#444444', linestyle='None',
                           markersize=8, label=r'Vertex (size $\propto\sqrt{\sum p_T^2}$)')],
    loc='upper right', title='Track / vertex types', bbox_to_anchor=(0.32, 0.95), fontsize=9)
ax.add_artist(hs_legend)
ax.grid(alpha=0.15, linestyle=':')
av_common_axes(
    ax, f"Event {event_num}: All Vertices and Tracks   "
        f"($\\langle\\mu\\rangle={mu_val:.0f}$, $N_{{\\rm vtx}}={n_vtx_total}$)")
av_save_two_views(fig, ax, f'tt_fig_{event_num}_all_vertices_styled')
plt.close(fig)

# =================================================================
# Version 2: "time-coloured" -- PU tracks coloured by reconstructed
# track time (Track_time, the quantity this timing ntuple was built for)
# =================================================================
valid_pu_times = np.array([t[5] for t in all_vtx_tracks if t[4] == 0 and t[6]])
if len(valid_pu_times) > 5:
    tnorm = mcolors.Normalize(vmin=np.percentile(valid_pu_times, 1),
                               vmax=np.percentile(valid_pu_times, 99))
else:
    tnorm = mcolors.Normalize(vmin=-1, vmax=1)
tcmap = cm.get_cmap('coolwarm')

fig, ax = plt.subplots(figsize=(15, 5.5))
for (Z, dz0, x, y, status, time, has_time, w) in all_vtx_tracks:
    if status == 1:
        color, lw = 'blue', 1.4
    elif status == 0 and has_time:
        color, lw = tcmap(tnorm(time)), 1.0
    else:
        color, lw = 'black', 0.8
    ax.plot([Z + dz0, Z + dz0 + x], [0, y], color=color, linewidth=lw)
av_draw_vertex_markers(ax, all_vtx_summary, sized=False)
ax.scatter(truth_vertices_z_full, [-0.75] * len(truth_vertices_z_full), color='black',
           marker='|', s=100, zorder=3)
sm = cm.ScalarMappable(norm=tnorm, cmap=tcmap)
sm.set_array([])
cbar = fig.colorbar(sm, ax=ax, pad=0.01)
cbar.set_label('PU track time [ps]')
hs_legend = ax.legend(
    handles=[mlines.Line2D([], [], color='blue', label='HS tracks (time not shown)')],
    loc='upper right', title='Track types', bbox_to_anchor=(0.32, 0.95), fontsize=9)
ax.add_artist(hs_legend)
av_common_axes(ax, f"Event {event_num}: Tracks coloured by reconstructed time "
                    f"($\\langle\\mu\\rangle={mu_val:.0f}$)")
av_save_two_views(fig, ax, f'tt_fig_{event_num}_all_vertices_time_colored')
plt.close(fig)

# =================================================================
# Version 3: vertex-level Z vs. time scatter
# =================================================================
fig, ax = plt.subplots(figsize=(9, 6.5))
zs = np.array([v[0] for v in all_vtx_summary])
sumpts = np.array([v[1] for v in all_vtx_summary])
mean_t = np.array([v[3] for v in all_vtx_summary])
sizes = 15 + 6.0 * np.sqrt(np.clip(sumpts, 0, None))
has_t = ~np.isnan(mean_t)
ax.scatter(zs[has_t], mean_t[has_t], s=sizes[has_t], color='#4a6fa5',
           alpha=0.75, edgecolor='black', linewidth=0.4, label='Reco vertices')
ax.set_xlabel('Reconstructed vertex Z [mm]')
ax.set_ylabel('Mean PU-track time [ps]')
ax.set_title(f"Event {event_num}: vertex Z vs.\\ time "
             f"(marker area $\\propto\\sum p_T^2$, $\\langle\\mu\\rangle={mu_val:.0f}$)")
ax.axvline(av_zoom_center, color='gray', linestyle=':', linewidth=1,
           label=f'zoom region ({av_zoom_xlim[0]:.0f}, {av_zoom_xlim[1]:.0f}) mm')
ax.grid(alpha=0.2, linestyle=':')
ax.legend(loc='upper right', fontsize=9)
fig.tight_layout()
fig.savefig(f'tt_fig_{event_num}_vertices_z_vs_time.png', dpi=150)
ax.set_xlim(*av_zoom_xlim)
in_zoom = (zs > av_zoom_xlim[0]) & (zs < av_zoom_xlim[1]) & has_t
if in_zoom.any():
    tmin, tmax = mean_t[in_zoom].min(), mean_t[in_zoom].max()
    tpad = 0.15 * max(tmax - tmin, 1.0)
    ax.set_ylim(tmin - tpad, tmax + tpad)
fig.savefig(f'tt_fig_{event_num}_vertices_z_vs_time_zoomed_in.png', dpi=150)
plt.close(fig)

print(f"\nSaved all-vertices suite (event {event_num}):")
print(f"  tt_fig_{event_num}_all_vertices.png / _zoomed_in.png")
print(f"  tt_fig_{event_num}_all_vertices_styled.png / _zoomed_in.png")
print(f"  tt_fig_{event_num}_all_vertices_time_colored.png / _zoomed_in.png")
print(f"  tt_fig_{event_num}_vertices_z_vs_time.png / _zoomed_in.png")

##############################################################################
######## Genuinely 3D interactive display for this event, every reco  ########
######## and truth vertex at its real (x, y, z), every track drawn as  #######
######## a schematic straight segment along its real (theta, phi)      #######
######## direction -- companion to event_display_all_vertices_VBF_3d.py ######
##############################################################################

COLOR_HS = '#2a78d6'
COLOR_PU = '#e34948'
COLOR_OTHER = '#898781'
COLOR_TRUTH = '#52514e'


def build_3d_scene(evnum):
    n_vtx_ev = len(my_branches.RecoVtx_z[evnum])
    vertices3d, tracks3d = [], []
    for vid in range(n_vtx_ev):
        vx = float(my_branches.RecoVtx_x[evnum][vid])
        vy = float(my_branches.RecoVtx_y[evnum][vid])
        vz = float(my_branches.RecoVtx_z[evnum][vid])
        sumpt2 = float(my_branches.RecoVtx_sumPt2[evnum][vid])
        is_hs = bool(my_branches.RecoVtx_isHS[evnum][vid])
        conn = my_branches.RecoVtx_track_idx[evnum][vid]
        for tidx in conn:
            th = float(my_branches.Track_theta[evnum][tidx])
            ph = float(my_branches.Track_phi[evnum][tidx])
            qop = float(my_branches.Track_qOverP[evnum][tidx])
            t_z0 = float(my_branches.Track_z0[evnum][tidx])
            truth_idx = my_branches.Track_truthVtx_idx[evnum][tidx]
            status = int(my_branches.TruthVtx_isHS[evnum][truth_idx]) if truth_idx != -1 else -1

            p = abs(1.0 / qop)
            eta = -math.log(math.tan(th / 2.0))
            pt = (p / math.cosh(eta)) / 1000.0
            # Schematic length (real track curvature/length ignored, same
            # convention as the 2D views): scale by sqrt(pT) for visibility.
            length = min(4.0 + 5.0 * math.sqrt(max(pt, 0.0)), 30.0)
            ux, uy, uz = math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)

            tracks3d.append(dict(
                x0=vx, y0=vy, z0=t_z0,
                x1=vx + length * ux, y1=vy + length * uy, z1=t_z0 + length * uz,
                status=status, vtxID=vid))
        vertices3d.append(dict(x=vx, y=vy, z=vz, sumpt2=sumpt2, is_HS=is_hs))

    truth3d = [dict(x=float(my_branches.TruthVtx_x[evnum][i]),
                     y=float(my_branches.TruthVtx_y[evnum][i]),
                     z=float(my_branches.TruthVtx_z[evnum][i]),
                     is_HS=bool(my_branches.TruthVtx_isHS[evnum][i]))
               for i in range(len(my_branches.TruthVtx_z[evnum]))]
    return vertices3d, tracks3d, truth3d


vertices3d, tracks3d, truth3d = build_3d_scene(event_num)
reco_pu_3d = [v for v in vertices3d if not v['is_HS']]
reco_hs_3d = [v for v in vertices3d if v['is_HS']]


def vsize3d(v):
    return 4 + 2.2 * math.sqrt(max(v['sumpt2'], 0.0))


# Plotly's 3D scene draws its "x" axis horizontally and its "z" axis
# vertically under the default camera; map the beamline (physics z, the
# long ~250 mm dimension) to plotly's x slot so it reads horizontally.
def to_plot3d(px, py, pz):
    return pz, px, py


traces3d = []

if truth3d:
    tx, ty, tz = to_plot3d([v['x'] for v in truth3d], [v['y'] for v in truth3d],
                            [v['z'] for v in truth3d])
    traces3d.append(go.Scatter3d(
        x=tx, y=ty, z=tz, mode='markers', name='Truth vertices',
        marker=dict(size=3, symbol='diamond', color=COLOR_TRUTH, opacity=0.75),
        hoverinfo='skip'))

if reco_pu_3d:
    vx, vy, vz = to_plot3d([v['x'] for v in reco_pu_3d], [v['y'] for v in reco_pu_3d],
                            [v['z'] for v in reco_pu_3d])
    traces3d.append(go.Scatter3d(
        x=vx, y=vy, z=vz, mode='markers', name='Reco vertices (PU)',
        marker=dict(size=[vsize3d(v) for v in reco_pu_3d], color=COLOR_OTHER,
                    opacity=0.8, line=dict(width=0.5, color='#3a3a38')),
        hoverinfo='skip'))

if reco_hs_3d:
    vx, vy, vz = to_plot3d([v['x'] for v in reco_hs_3d], [v['y'] for v in reco_hs_3d],
                            [v['z'] for v in reco_hs_3d])
    traces3d.append(go.Scatter3d(
        x=vx, y=vy, z=vz, mode='markers', name='Reco vertex (hard-scatter)',
        marker=dict(size=[vsize3d(v) + 4 for v in reco_hs_3d], color=COLOR_HS, symbol='diamond',
                    opacity=0.95, line=dict(width=1, color='#0b0b0b')),
        hoverinfo='skip'))


def line_trace3d(subset, **kw):
    xs, ys, zs = [], [], []
    for t in subset:
        px0, py0, pz0 = to_plot3d(t['x0'], t['y0'], t['z0'])
        px1, py1, pz1 = to_plot3d(t['x1'], t['y1'], t['z1'])
        xs += [px0, px1, None]
        ys += [py0, py1, None]
        zs += [pz0, pz1, None]
    return go.Scatter3d(x=xs, y=ys, z=zs, mode='lines', **kw)


hs_tracks3d = [t for t in tracks3d if t['status'] == 1]
pu_tracks3d = [t for t in tracks3d if t['status'] == 0]
other_tracks3d = [t for t in tracks3d if t['status'] not in (0, 1)]

if hs_tracks3d:
    traces3d.append(line_trace3d(hs_tracks3d, name='HS tracks',
                                  line=dict(color=COLOR_HS, width=4), hoverinfo='skip'))
if other_tracks3d:
    traces3d.append(line_trace3d(other_tracks3d, name='Other tracks',
                                  line=dict(color=COLOR_OTHER, width=2), opacity=0.5,
                                  hoverinfo='skip'))
if pu_tracks3d:
    traces3d.append(line_trace3d(pu_tracks3d, name='PU tracks',
                                  line=dict(color=COLOR_PU, width=3), hoverinfo='skip'))

fig3d = go.Figure(data=traces3d)
fig3d.update_layout(
    template=None,
    scene=dict(
        xaxis=dict(title='z [mm]', backgroundcolor='rgba(0,0,0,0)',
                   gridcolor='#e1e0d9', zerolinecolor='#c3c2b7', color='#52514e'),
        yaxis=dict(title='x [mm] (schematic)', backgroundcolor='rgba(0,0,0,0)',
                   gridcolor='#e1e0d9', zerolinecolor='#c3c2b7', color='#52514e'),
        zaxis=dict(title='y [mm] (schematic)', backgroundcolor='rgba(0,0,0,0)',
                   gridcolor='#e1e0d9', zerolinecolor='#c3c2b7', color='#52514e'),
        aspectmode='manual', aspectratio=dict(x=2.4, y=1, z=1),
        camera=dict(eye=dict(x=0.9, y=1.5, z=1.5)),
    ),
    paper_bgcolor='#fcfcfb', plot_bgcolor='#fcfcfb',
    # A single simple font name avoids a known Plotly gl3d WebGL text-atlas
    # bug where compound/quoted CSS font stacks render as garbled glyphs.
    font=dict(family='Arial, sans-serif', color='#0b0b0b'),
    legend=dict(bgcolor='rgba(252,252,251,0.85)', bordercolor='#e1e0d9', borderwidth=1),
    margin=dict(l=0, r=0, t=10, b=0),
    height=760,
)

plotly_js_path = os.path.join(os.path.dirname(plotly.__file__), 'package_data', 'plotly.min.js')
with open(plotly_js_path, 'rb') as fh:
    plotly_js_b64 = base64.b64encode(fh.read()).decode('ascii')
chart_html_3d = (f'<script src="data:text/javascript;base64,{plotly_js_b64}"></script>\n'
                  + fig3d.to_html(full_html=False, include_plotlyjs=False,
                                   div_id='tt-vertex-3d-chart',
                                   config={'responsive': True, 'displaylogo': False}))

page_html_3d = f"""<title>Event {event_num} Vertex Display (ttbar)</title>
<style>
body{{font-family:Arial,sans-serif;background:#f9f9f7;color:#0b0b0b;margin:0;padding:1.5rem;}}
p{{max-width:75ch;color:#52514e;}}
.stats{{display:flex;gap:1.5rem;flex-wrap:wrap;margin:0.5rem 0 1rem;font-size:0.9rem;color:#52514e;}}
.stats b{{color:#0b0b0b;}}
</style>
<h2>Event {event_num}: interactive vertex display (ttbar, CaloTiming ntuple)</h2>
<p>Every reconstructed and truth vertex plotted at its real (x, y, z) position; each track
drawn as a schematic straight segment along its true (&theta;, &phi;) direction (magnetic
curvature ignored). Drag to orbit, scroll to zoom, click a legend entry to hide/show a layer.</p>
<div class="stats">
<span>Reco vertices: <b>{n_vtx_total}</b></span>
<span>Hard-scatter vtx: <b>{len(reco_hs_3d)}</b></span>
<span>Truth vertices: <b>{len(truth3d)}</b></span>
<span>Tracks drawn: <b>{len(tracks3d)}</b></span>
<span>&lang;&mu;&rang;: <b>{mu_val:.0f}</b></span>
</div>
{chart_html_3d}
"""

out_path_3d = f'tt_fig_{event_num}_all_vertices_3d_interactive.html'
with open(out_path_3d, 'w') as fh:
    fh.write(page_html_3d)
print(f"\nWrote interactive 3D page to {out_path_3d}")



