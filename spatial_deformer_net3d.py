# -*- coding: utf-8 -*-
"""
Created on Wed Mar  7 15:13:36 2018

@author: Dongyang

A 3d version of spatial deformer network
"""

from keras.layers.core import Layer
import tensorflow as tf


class SpatialDeformer3D(Layer):

    def __init__(self,
                 localization_net, # this suppose to produce a deformation with 3 channels
                 output_size,
                 **kwargs):
        self.locnet = localization_net
        self.output_size = output_size
        super(SpatialDeformer3D, self).__init__(**kwargs)

    def build(self, input_shape):
        self.locnet.build(input_shape)
        self.trainable_weights = self.locnet.trainable_weights
        super(SpatialDeformer3D, self).build(input_shape)

    def compute_output_shape(self, input_shape):
        output_size = self.output_size
        return (None,
                int(output_size[0]), # width
                int(output_size[1]), # height
                int(output_size[2]), # depth
                1, #brutally change it to one exlucding the stacked second grey image
#                int(input_shape[-1])
                )  

    def call(self, X, mask=None): 
        deformation = self.locnet.call(X)
        Y = tf.expand_dims(X[:,:,:,:,0], 4) # only transform the first channel
        output = self._transform(deformation, Y, self.output_size) 
        return output

    def _repeat(self, x, num_repeats): # copy along the second dimension, each row is a copy of an index
        ones = tf.ones((1, num_repeats), dtype='int32')
        x = tf.reshape(x, shape=(-1,1))
        x = tf.matmul(x, ones)
        return tf.reshape(x, [-1])

    def _interpolate(self, image, x, y, z, output_size):  # tri-linear interpolation
        batch_size = tf.shape(image)[0]
        height = tf.shape(image)[1]
        width = tf.shape(image)[2]
        depth = tf.shape(image)[3]
        num_channels = tf.shape(image)[4]

        x = tf.cast(x , dtype='float32')
        y = tf.cast(y , dtype='float32')
        z = tf.cast(z , dtype='float32')

        height_float = tf.cast(height, dtype='float32')
        width_float = tf.cast(width, dtype='float32')
        depth_float = tf.cast(depth, dtype='float32')

        output_height = output_size[0]
        output_width  = output_size[1]
        output_depth = output_size[2]

        x = .5*(x + 1.0)*(width_float)
        y = .5*(y + 1.0)*(height_float)
        z = .5*(z + 1.0)*(depth_float)

        x0 = tf.cast(tf.floor(x), 'int32')
        x1 = x0 + 1
        y0 = tf.cast(tf.floor(y), 'int32')
        y1 = y0 + 1
        z0 = tf.cast(tf.floor(z), 'int32')
        z1 = z0 + 1
        
        max_z = tf.cast(depth - 1,  dtype='int32')
        max_y = tf.cast(height - 1, dtype='int32')
        max_x = tf.cast(width - 1,  dtype='int32')
        
        zero = tf.zeros([], dtype='int32')

        x0 = tf.clip_by_value(x0, zero, max_x)
        x1 = tf.clip_by_value(x1, zero, max_x)
        y0 = tf.clip_by_value(y0, zero, max_y)
        y1 = tf.clip_by_value(y1, zero, max_y)
        z0 = tf.clip_by_value(z0, zero, max_z)
        z1 = tf.clip_by_value(z1, zero, max_z)

        
        xyslice_dimensions = width*height
        flat_image_dimensions = xyslice_dimensions*depth
        pixels_batch = tf.range(batch_size)*flat_image_dimensions
        flat_output_dimensions = output_height*output_width*output_depth
        base = self._repeat(pixels_batch, flat_output_dimensions)
        
        
        #get indices for the eight corners       
        
        # the slice (depth)
        base_z0 = base + z0*xyslice_dimensions
        base_z1 = base + z1*xyslice_dimensions        
        
        # row in each slice
        base_00 = base_z0 + y0*width
        base_01 = base_z0 + y1*width
        base_10 = base_z1 + y0*width
        base_11 = base_z1 + y1*width
 
        # each indices
        indices_000 = base_00 + x0
        indices_001 = base_00 + x1
        indices_010 = base_01 + x0
        indices_011 = base_01 + x1
        indices_100 = base_10 + x0
        indices_101 = base_10 + x1
        indices_110 = base_11 + x0
        indices_111 = base_11 + x1             

        flat_image = tf.reshape(image, shape=(-1, num_channels))
        flat_image = tf.cast(flat_image, dtype='float32')
        
        pixel_values_000 = tf.gather(flat_image, indices_000)
        pixel_values_001 = tf.gather(flat_image, indices_001)
        pixel_values_010 = tf.gather(flat_image, indices_010)
        pixel_values_011 = tf.gather(flat_image, indices_011)          
        pixel_values_100 = tf.gather(flat_image, indices_100)
        pixel_values_101 = tf.gather(flat_image, indices_101)
        pixel_values_110 = tf.gather(flat_image, indices_110)
        pixel_values_111 = tf.gather(flat_image, indices_111)       
        
        
        x0 = tf.cast(x0, 'float32')
        x1 = tf.cast(x1, 'float32')
        y0 = tf.cast(y0, 'float32')
        y1 = tf.cast(y1, 'float32')
        z0 = tf.cast(z0, 'float32')
        z1 = tf.cast(z1, 'float32')
        
        
        vol_000 = tf.expand_dims((x1-x)*(y1-y)*(z1-z) , 1)
        vol_001 = tf.expand_dims((x1-x)*(y1-y)*(z-z0) , 1)
        vol_010 = tf.expand_dims((x1-x)*(y-y0)*(z1-z) , 1)
        vol_011 = tf.expand_dims((x1-x)*(y-y0)*(z-z0) , 1)
        vol_100 = tf.expand_dims((x-x0)*(y1-y)*(z1-z) , 1)
        vol_101 = tf.expand_dims((x-x0)*(y1-y)*(z-z0) , 1)
        vol_110 = tf.expand_dims((x-x0)*(y-y0)*(z1-z) , 1)
        vol_111 = tf.expand_dims((x-x0)*(y-y0)*(z-z0) , 1)
       
        
        output = tf.add_n([vol_000*pixel_values_000,
                           vol_001*pixel_values_001,
                           vol_010*pixel_values_010,
                           vol_011*pixel_values_011,
                           vol_100*pixel_values_100,
                           vol_101*pixel_values_101,
                           vol_110*pixel_values_110,
                           vol_111*pixel_values_111,
                           ])
     
        return output

    def _meshgrid(self, height, width, depth):
        x_linspace = tf.linspace(-1., 1., width)
        y_linspace = tf.linspace(-1., 1., height)
        z_linspace = tf.linspace(-1., 1., depth)
        
        x_coordinates, y_coordinates, z_coordinates = tf.meshgrid(x_linspace, y_linspace, z_linspace)
        
        x_coordinates = tf.reshape(x_coordinates, [-1])
        y_coordinates = tf.reshape(y_coordinates, [-1])
        z_coordinates = tf.reshape(z_coordinates, [-1])

        indices_grid = tf.concat([x_coordinates, y_coordinates, z_coordinates], 0
                                 )
        return indices_grid

    def _transform(self, deformation, input_vol, output_size):
        batch_size = tf.shape(input_vol)[0]
        height = tf.shape(input_vol)[1]
        width = tf.shape(input_vol)[2]
        depth = tf.shape(input_vol)
        num_channels = tf.shape(input_vol)[3]


        width = tf.cast(width, dtype='float32')
        height = tf.cast(height, dtype='float32')
        depth = tf.cast(depth, dtype = 'float32')
        
        output_height = output_size[0]
        output_width = output_size[1]
        output_depth = output_size[2]
        
        indices_grid = self._meshgrid(output_height, output_width, output_depth)

        indices_grid = tf.tile(indices_grid, tf.stack([batch_size]))
        indices_grid = tf.reshape(indices_grid, (batch_size, 3, -1))



        deformation = tf.reshape(deformation, (-1, output_height * output_width * output_depth, 3))
        deformation = tf.transpose(deformation, (0, 3, 1))

        
        transformed_grid = indices_grid + deformation # are they of the same shape?
        x_s = tf.slice(transformed_grid, [0, 0, 0], [-1, 1, -1]) #problem here?
        y_s = tf.slice(transformed_grid, [0, 1, 0], [-1, 1, -1])
        z_s = tf.slice(transformed_grid, [0, 2, 0], [-1, 1, -1])
        x_s_flatten = tf.reshape(x_s, [-1])
        y_s_flatten = tf.reshape(y_s, [-1])
        z_s_flatten = tf.reshape(z_s, [-1])

        transformed_image = self._interpolate(input_vol, # modify so it only transform the first channel?
                                                x_s_flatten,
                                                y_s_flatten,
                                                z_s_flatten,
                                                output_size)

        transformed_image = tf.reshape(transformed_image, shape=(batch_size,
                                                                output_height,
                                                                output_width,
                                                                output_depth,
                                                                num_channels))
        return transformed_image
