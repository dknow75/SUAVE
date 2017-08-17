## @ingroup Methods-Missions-Segments-Common
# Frames.py
# 
# Created:  Jul 2014, SUAVE Team
# Modified: Jul 2016, E. Botero
#           Jul 2017, E. Botero

# ----------------------------------------------------------------------
#  Imports
# ----------------------------------------------------------------------

import autograd.numpy as np 
from SUAVE.Core import Units

from SUAVE.Methods.Geometry.Three_Dimensional \
     import angles_to_dcms, orientation_product, orientation_transpose

# ----------------------------------------------------------------------
#  Initialize Inertial Position
# ----------------------------------------------------------------------

## @ingroup Methods-Missions-Segments-Common
def initialize_inertial_position(segment,state):
    """ Sets the initial location of the vehicle at the start of the segment
    
        Assumptions:
        Only used if there is an initial condition
        
        Inputs:
            state.initials.conditions:
                frames.inertial.position_vector   [meters]
            state.conditions:           
                frames.inertial.position_vector   [meters]
            
        Outputs:
            state.conditions:           
                frames.inertial.position_vector   [meters]

        Properties Used:
        N/A
                                
    """    
    
    if state.initials:
        r_initial = state.initials.conditions.frames.inertial.position_vector
        r_current = state.conditions.frames.inertial.position_vector
        
        state.conditions.frames.inertial.position_vector[:,:] = r_current + (r_initial[-1,None,:] - r_current[0,None,:])# Update for AD
    
    return
    
    
# ----------------------------------------------------------------------
#  Initialize Time
# ----------------------------------------------------------------------

## @ingroup Methods-Missions-Segments-Common
def initialize_time(segment,state):
    """ Sets the initial time of the vehicle at the start of the segment
    
        Assumptions:
        Only used if there is an initial condition
        
        Inputs:
            state.initials.conditions:
                frames.inertial.time     [seconds]
                frames.planet.start_time [seconds]
            state.conditions:           
                frames.inertial.time     [seconds]
            segment.start_time           [seconds]
            
        Outputs:
            state.conditions:           
                frames.inertial.time     [seconds]
                frames.planet.start_time [seconds]

        Properties Used:
        N/A
                                
    """        
    
    if state.initials:
        t_initial = state.initials.conditions.frames.inertial.time
        t_current = state.conditions.frames.inertial.time
        
        state.conditions.frames.inertial.time[:,:] = t_current + (t_initial[-1,0] - t_current[0,0]) # Update for AD
        
    else:
        t_initial = state.conditions.frames.inertial.time[0,0]
        
    if state.initials:
        state.conditions.frames.planet.start_time = state.initials.conditions.frames.planet.start_time
        
    elif segment.has_key('start_time'):
        state.conditions.frames.planet.start_time = segment.start_time
    
    return
    

# ----------------------------------------------------------------------
#  Initialize Planet Position
# ----------------------------------------------------------------------

## @ingroup Methods-Missions-Segments-Common
def initialize_planet_position(segment,state):
    """ Sets the initial location of the vehicle relative to the planet at the start of the segment
    
        Assumptions:
        Only used if there is an initial condition
        
        Inputs:
            state.initials.conditions:
                frames.planet.longitude [Radians]
                frames.planet.latitude  [Radians]
            segment.longitude           [Radians]
            segment.latitude            [Radians]

        Outputs:
            state.conditions:           
                frames.planet.latitude  [Radians]
                frames.planet.longitude [Radians]

        Properties Used:
        N/A
                                
    """        
    
    if state.initials:
        longitude_initial = state.initials.conditions.frames.planet.longitude[-1,0]
        latitude_initial  = state.initials.conditions.frames.planet.latitude[-1,0] 
    elif segment.has_key('latitude'):
        longitude_initial = segment.longitude
        latitude_initial  = segment.latitude      
    else:
        longitude_initial = 0.0
        latitude_initial  = 0.0


    state.conditions.frames.planet.longitude = longitude_initial
    state.conditions.frames.planet.latitude  = latitude_initial    

    return
    
    
# ----------------------------------------------------------------------
#  Update Planet Position
# ----------------------------------------------------------------------

## @ingroup Methods-Missions-Segments-Common
def update_planet_position(segment,state):
    """ Updates the location of the vehicle relative to the Planet throughout the mission
    
        Assumptions:
        This is valid for small movements and times as it does not account for the rotation of the Planet beneath the vehicle
        
        Inputs:
        state.conditions:
            freestream.velocity                      [meters/second]
            freestream.altitude                      [meters]
            frames.body.inertial_rotations           [Radians]
        segment.analyses.planet.features.mean_radius [meters]
        state.numerics.time.integrate                [float]
            
        Outputs:
            state.conditions:           
                frames.planet.latitude  [Radians]
                frames.planet.longitude [Radians]

        Properties Used:
        N/A
                                
    """        
    
    # unpack
    conditions = state.conditions
    
    # unpack orientations and velocities
    V          = conditions.freestream.velocity[:,0]
    altitude   = conditions.freestream.altitude[:,0]
    phi        = conditions.frames.body.inertial_rotations[:,0]
    theta      = conditions.frames.body.inertial_rotations[:,1]
    psi        = conditions.frames.body.inertial_rotations[:,2]
    alpha      = conditions.aerodynamics.angle_of_attack[:,0]
    I          = state.numerics.time.integrate
    Re         = segment.analyses.planet.features.mean_radius

    # The flight path and radius
    gamma     = theta - alpha
    R         = altitude + Re

    # Find the velocities and integrate the positions
    lamdadot  = (V/R)*np.cos(gamma)*np.cos(psi)
    lamda     = np.dot(I,lamdadot) * 180./np.pi # Latitude
    mudot     = (V/R)*np.cos(gamma)*np.sin(psi)/np.cos(lamda)
    mu        = np.dot(I,mudot) * 180./np.pi # Longitude

    # Reshape the size of the vectorss
    shape     = np.shape(conditions.freestream.velocity)
    mu        = np.reshape(mu,shape)
    lamda     = np.reshape(lamda,shape)

    # Pack'r up
    lat = conditions.frames.planet.latitude
    lon = conditions.frames.planet.longitude
    conditions.frames.planet.latitude  = lat + lamda
    conditions.frames.planet.longitude = lon + mu

    return
    
    
# ----------------------------------------------------------------------
#  Update Orientations
# ----------------------------------------------------------------------

## @ingroup Methods-Missions-Segments-Common
def update_orientations(segment,state):
    
    """ Updates the orientation of the vehicle throughout the mission for each relevant axis
    
        Assumptions:
        This assumes the vehicle has 3 frames: inertial, body, and wind. There also contains bits for stability axis which are not used. Creates tensors and solves for alpha and beta.
        
        Inputs:
        state.conditions:
            frames.inertial.velocity_vector          [meters/second]
            frames.body.inertial_rotations           [Radians]
        segment.analyses.planet.features.mean_radius [meters]
        state.numerics.time.integrate                [float]
            
        Outputs:
            state.conditions:           
                aerodynamics.angle_of_attack      [Radians]
                aerodynamics.side_slip_angle      [Radians]
                aerodynamics.roll_angle           [Radians]
                frames.body.transform_to_inertial [Radians]
                frames.wind.body_rotations        [Radians]
                frames.wind.transform_to_inertial [Radians]
    

        Properties Used:
        N/A
    """

    # unpack
    conditions = state.conditions
    V_inertial = conditions.frames.inertial.velocity_vector
    body_inertial_rotations = conditions.frames.body.inertial_rotations

    # ------------------------------------------------------------------
    #  Body Frame
    # ------------------------------------------------------------------

    # body frame rotations
    zeros = state.ones_row(1) * 0.0
    phi   = body_inertial_rotations[:,0,None]
    theta = body_inertial_rotations[:,1,None]
    psi   = body_inertial_rotations[:,2,None]

    # body frame tranformation matrices
    T_inertial2body = angles_to_dcms(body_inertial_rotations,(2,1,0))
    T_body2inertial = orientation_transpose(T_inertial2body)

    # transform inertial velocity to body frame
    V_body = orientation_product(T_inertial2body,V_inertial)

    # project inertial velocity into body x-z plane
    V_stability = np.transpose(np.array((V_body[:,0],zeros[:,0],V_body[:,2])))
    V_stability_magnitude = np.sqrt( np.sum(V_stability**2,axis=1) )[:,None]
    #V_stability_direction = V_stability / V_stability_magnitude

    # calculate angle of attack
    alpha = np.arctan(V_stability[:,2]/V_stability[:,0])[:,None]

    # calculate side slip
    beta = np.arctan(V_body[:,1]/V_stability_magnitude[:,0])[:,None]

    # pack aerodynamics angles
    conditions.aerodynamics.angle_of_attack = alpha
    conditions.aerodynamics.side_slip_angle = beta
    conditions.aerodynamics.roll_angle      = phi

    # pack transformation tensor
    conditions.frames.body.transform_to_inertial = T_body2inertial


    # ------------------------------------------------------------------
    #  Wind Frame
    # ------------------------------------------------------------------

    # back calculate wind frame rotations    
    wind_body_rotations = np.transpose(np.array((zeros[:,0],alpha[:,0],beta[:,0])))
    
    # wind frame tranformation matricies
    T_wind2body = angles_to_dcms(wind_body_rotations,(2,1,0))
    T_body2wind = orientation_transpose(T_wind2body)
    T_wind2inertial = orientation_product(T_wind2body,T_body2inertial)

    # pack wind rotations
    conditions.frames.wind.body_rotations = wind_body_rotations

    # pack transformation tensor
    conditions.frames.wind.transform_to_inertial = T_wind2inertial
    
    return
        

# ----------------------------------------------------------------------
#  Update Forces
# ----------------------------------------------------------------------

## @ingroup Methods-Missions-Segments-Common
def update_forces(segment,state):
    
    """ Summation of forces: lift, drag, thrust, weight. Future versions will include new definitions of dreams, FAA, money, and reality.
    
        Assumptions:
        You only have these 4 forces applied to the vehicle
        
        Inputs:
        state.conditions:
            frames.wind.lift_force_vector          [newtons]
            frames.wind.drag_force_vector          [newtons]
            frames.inertial.gravity_force_vector   [newtons]
            frames.body.thrust_force_vector        [newtons]
            frames.body.transform_to_inertial      [newtons]
            frames.wind.transform_to_inertial      [newtons]

            
        Outputs:
            state.conditions:           
                frames.inertial.total_force_vector [newtons]

    

        Properties Used:
        N/A
    """    

    # unpack
    conditions = state.conditions

    # unpack forces
    wind_lift_force_vector        = conditions.frames.wind.lift_force_vector
    wind_drag_force_vector        = conditions.frames.wind.drag_force_vector
    body_thrust_force_vector      = conditions.frames.body.thrust_force_vector
    inertial_gravity_force_vector = conditions.frames.inertial.gravity_force_vector

    # unpack transformation matrices
    T_body2inertial = conditions.frames.body.transform_to_inertial
    T_wind2inertial = conditions.frames.wind.transform_to_inertial

    # to inertial frame
    L = orientation_product(T_wind2inertial,wind_lift_force_vector)
    D = orientation_product(T_wind2inertial,wind_drag_force_vector)
    T = orientation_product(T_body2inertial,body_thrust_force_vector)
    W = inertial_gravity_force_vector

    # sum of the forces
    F = L + D + T + W
    # like a boss

    # pack
    conditions.frames.inertial.total_force_vector = F

    return

# ----------------------------------------------------------------------
#  Integrate Position
# ----------------------------------------------------------------------

## @ingroup Methods-Missions-Segments-Common
def integrate_inertial_horizontal_position(segment,state):
    """ Determines how far the airplane has traveled. 
    
        Assumptions:
        Assumes a flat earth, this is planar motion.
        
        Inputs:
            state.conditions:
                frames.inertial.position_vector [meters]
                frames.inertial.velocity_vector [meters/second]
            state.numerics.time.integrate       [float]
            
        Outputs:
            state.conditions:           
                frames.inertial.position_vector [meters]

        Properties Used:
        N/A
                                
    """        

    # unpack
    conditions = state.conditions
    x0 = conditions.frames.inertial.position_vector[0,None,0:1+1]
    vx = conditions.frames.inertial.velocity_vector[:,0:1+1]
    I  = state.numerics.time.integrate
    
    # integrate
    x = np.dot(I,vx) + x0
    
    # pack
    conditions.frames.inertial.position_vector[:,0:1+1] = x[:,:] # Update for AD
    
    return

# ----------------------------------------------------------------------
#  Update Acceleration
# ----------------------------------------------------------------------

## @ingroup Methods-Missions-Segments-Common
def update_acceleration(segment,state):
    """ Differentiates the velocity vector to get accelerations
    
        Assumptions:
        Assumes a flat earth, this is planar motion.
        
        Inputs:
            state.conditions:
                frames.inertial.velocity_vector     [meters/second]
            state.numerics.time.differentiate       [float]
            
        Outputs:
            state.conditions:           
                frames.inertial.acceleration_vector [meters]

        Properties Used:
        N/A
                                
    """            
    
    # unpack conditions
    v = state.conditions.frames.inertial.velocity_vector
    D = state.numerics.time.differentiate
    
    # accelerations
    acc = np.dot(D,v)
    
    # pack conditions
    state.conditions.frames.inertial.acceleration_vector[:,:] = acc[:,:]   # Update for AD