from threading import local
from attr import assoc
from prob_pairwise_measures import ProbabilityPairwiseMeasures
from pairwise_measures import BinaryPairwiseMeasures, MultiClassPairwiseMeasures
from association_localization import AssociationMapping
import numpy as np
import pandas as pd



class MixedLocSegPairwiseMeasure(object):
    def __init__(self, pred, ref, list_predimg, list_refimg, pred_prob, measures_overlap=[],measures_boundary=[], measures_mt=[],measures_pcc=[],measures_detseg=[], num_neighbors=8, pixdim=[1, 1, 1],
                 empty=False, dict_args={}):
        self.pred = pred
        self.ref = ref
        self.predimg = list_predimg
        self.refimg = list_refimg
        self.measures_mt = measures_mt
        self.measures_detseg = measures_detseg
        self.measures_det = measures_pcc
        self.measures_seg = measures_boundary + measures_overlap
        self.dict_args = dict_args
        self.prob_res = ProbabilityPairwiseMeasures(pred_prob, ref, self.measures_mt, self.dict_args)
        self.det_res = BinaryPairwiseMeasures(pred, ref, self.measures_det)
        self.seg_res = [BinaryPairwiseMeasures(p,r, self.measures_seg) for (p,r) in zip(list_predimg, list_refimg)]

    def average_iou_img(self):
        list_iou = []
        for (p, r) in zip(self.predimg, self.refimg):
            PE = BinaryPairwiseMeasures(p,r)
            list_iou.append(PE.intersection_over_union())
        return np.mean(np.asarray(list_iou))

    def recognition_quality(self):
        PE = BinaryPairwiseMeasures(self.pred,self.ref)
        return PE.fbeta()

    def panoptic_quality(self):
        return self.recognition_quality() * self.average_iou_img()

    def to_dict_mt(self):
        dict_output = self.prob_res.to_dict_meas()
        return dict_output

    def to_dict_det(self):
        dict_output = self.det_res.to_dict_meas()
        if 'PQ' in self.measures_detseg:
            dict_output['PQ'] = self.panoptic_quality()
        return dict_output

    def to_pd_seg(self):
        list_res = []
        for ps in self.seg_res:
            dict_tmp = ps.to_dict_meas()
            list_res.append(dict_tmp)
        return pd.DataFrame.from_dict(list_res)

class MultiLabelLocSegPairwiseMeasure(object):
    # Instance segmentation
    def __init__(self, pred_class, ref_class, pred_loc, ref_loc, pred_prob, list_values,
                 measures_pcc=[], measures_overlap=[] ,measures_boundary=[], measures_mt=[], per_case=True, num_neighbors=8, pixdim=[1, 1, 1],
                 empty=False, association='Greedy IoU', localization='iou'):
        self.pred_loc = pred_loc
        self.list_values = list_values
        self.ref_class = ref_class
        self.ref_loc = ref_loc
        self.pred_prob = pred_prob
        self.pred_class = pred_class
        self.measures_prob = measures_mt
        self.measures_det = measures_pcc
        self.measures_seg = measures_overlap + measures_boundary
        self.per_case = per_case
        self.association = association
        self.localization = localization

    def per_label_dict(self):
        list_det = []
        list_seg = []
        for lab in self.list_values:
            list_pred = []
            list_ref = []
            list_prob = []
            list_pred_loc = []
            list_ref_loc = []
            for case in range(len(self.pred_class)):
                ind_pred = np.where(self.pred_class[case] == lab)
                pred_tmp = np.where(self.pred_class[case] == lab, np.ones_like(self.pred_class[case]), np.zeros_like(self.pred_class[case]))
                ref_tmp = np.where(self.ref_class[case] == lab, np.ones_like(self.ref_class[case]), np.zeros_like(self.ref_class[case]))
                ind_ref = np.where(self.ref_class[case] == lab)
                pred_loc_tmp = self.pred_loc[case][ind_pred[0]]
                ref_loc_tmp = self.ref_loc[case][ind_ref[0]]
                pred_prob_tmp = self.pred_prob[case][ind_pred[0]]
                AS = AssociationMapping(pred_loc=pred_loc_tmp, ref_loc=ref_loc_tmp, pred_prob=pred_prob_tmp, association=self.association, localization=self.localization)
                pred_tmp_fin = np.asarray(AS.df_matching['pred'])
                pred_tmp_fin = np.where(pred_tmp_fin>-1, np.ones_like(pred_tmp_fin),np.zeros_like(pred_tmp_fin))
                ref_tmp_fin = np.asarray(AS.df_matching['ref'])
                ref_tmp_fin = np.where(ref_tmp_fin>-1, np.ones_like(ref_tmp_fin), np.zeros_like(ref_tmp_fin))
                pred_loc_tmp_fin, ref_loc_tmp_fin = AS.matching_ref_predseg()
                if self.per_case:
            # pred_loc_tmp_fin = pred_loc_tmp[list_valid]
            # list_ref_valid = list(df_matching[df_matching['seg'].isin(list_valid)]['ref'])
            # ref_loc_tmp_fin = ref_loc_tmp[list_ref_valid]

                    MLSPM = MixedLocSegPairwiseMeasure(pred=pred_tmp_fin, ref=ref_tmp_fin,
                                                       list_predimg=pred_loc_tmp_fin,
                                                       list_refimg=ref_loc_tmp_fin,measures_det=self.measures_det,
                                                       measures_seg=self.measures_seg)
                    seg_res = MLSPM.to_pd_seg()
                    seg_res['label'] = lab
                    seg_res['case'] = case
                    det_res = MLSPM.to_dict_det()
                    det_res['label'] = lab
                    det_res['case'] = case
                    list_det.append(det_res)
                    list_seg.append(seg_res)
                else:
                    for p in pred_loc_tmp_fin:
                        list_pred_loc.append(p)
                    for r in ref_loc_tmp_fin:
                        list_ref_loc.append(r)
                    for p in pred_tmp_fin:
                        list_pred.append(p)
                    for r in ref_tmp_fin:
                        list_ref.append(r)
                    for p in pred_prob_tmp:
                        list_prob.append(p)
            if not self.per_case:
                MLSPM = MixedLocSegPairwiseMeasure(pred=list_pred, ref=list_ref,
                                                   list_predimg=list_pred_loc,
                                                   list_refimg=list_ref_loc, measures_det=self.measures_det,
                                                   measures_seg=self.measures_seg)
                res_seg = MLSPM.to_pd_seg()
                res_seg['label'] = lab
                res_det = MLSPM.to_dict_det()
                res_det['label'] = lab
                list_det.append(res_det)
                list_seg.append(res_seg)
        return pd.concat(list_seg), pd.DataFrame.from_dict(list_det)

class MultiLabelLocMeasures(object):
    def __init__(self, pred_loc, ref_loc, pred_class, ref_class, pred_prob, list_values, measures_pcc=[],measures_mt=[],per_case=False, association='Greedy IoU',localization='iou'):
        self.pred_loc = pred_loc
        self.ref_loc = ref_loc
        self.ref_class = ref_class
        self.pred_class = pred_class
        self.list_values = list_values
        self.pred_prob = pred_prob
        self.measures_pcc=measures_pcc
        self.measures_mt = measures_mt
        self.per_case=per_case
        self.association=association
        self.localization=localization

    def per_label_dict(self):
        list_det = []
        list_mt = []
        for lab in self.list_values:
            list_pred = []
            list_ref = []
            list_prob = []
            for case in range(len(self.ref_class)):
                pred_arr = np.asarray(self.pred_class[case])
                ref_arr = np.asarray(self.ref_class[case])
                ind_pred = np.where(pred_arr == lab)
                pred_tmp = np.where(pred_arr == lab, np.ones_like(pred_arr), np.zeros_like(pred_arr))
                ref_tmp = np.where(ref_arr == lab, np.ones_like(ref_arr), np.zeros_like(ref_arr))
                ind_ref = np.where(ref_arr == lab)
                pred_loc_tmp = [self.pred_loc[case][f] for f in ind_pred[0]]
                ref_loc_tmp = [self.ref_loc[case][f] for f in ind_ref[0]]
                pred_prob_tmp = [self.pred_prob[case][f] for f in ind_pred[0]]
                AS = AssociationMapping(pred_loc=pred_loc_tmp, ref_loc=ref_loc_tmp, pred_prob=pred_prob_tmp, association=self.association, localization=self.localization)
                df_matching = AS.df_matching
                pred_tmp_fin = np.asarray(df_matching['pred'])
                pred_tmp_fin = np.where(pred_tmp_fin>-1, np.ones_like(pred_tmp_fin),np.zeros_like(pred_tmp_fin))
                ref_tmp_fin = np.asarray(df_matching['ref'])
                ref_tmp_fin = np.where(ref_tmp_fin>-1, np.ones_like(ref_tmp_fin), np.zeros_like(ref_tmp_fin))
                pred_prob_tmp_fin = np.asarray(df_matching['pred_prob'])
                if self.per_case:

                    BPM = BinaryPairwiseMeasures(pred=pred_tmp_fin, ref=ref_tmp_fin, measures=self.measures_pcc)
                    det_res = BPM.to_dict_meas()
                    det_res['label'] = lab
                    det_res['case'] = case
                    list_det.append(det_res)
                    PPM = ProbabilityPairwiseMeasures(pred_prob_tmp_fin, ref_tmp_fin,measures=self.measures_mt)
                    mt_res = PPM.to_dict_meas()
                    mt_res['label'] = lab
                    mt_res['case'] = case
                    list_mt.append(mt_res)
                else:
                    list_pred.append(pred_tmp_fin)
                    list_ref.append(ref_tmp_fin)
                    list_prob.append(pred_prob_tmp_fin)
            if not self.per_case:
                overall_pred = np.concatenate(list_pred)
                overall_ref = np.concatenate(list_ref)
                overall_prob = np.concatenate(list_prob)
                BPM = BinaryPairwiseMeasures(pred=overall_pred, ref=overall_ref,measures=self.measures_pcc)
                det_res = BPM.to_dict_meas()
                det_res['label'] = lab
                list_det.append(det_res)
                PPM = ProbabilityPairwiseMeasures(pred_prob_tmp_fin, ref_tmp_fin,measures=self.measures_mt)
                mt_res = PPM.to_dict_meas()
                mt_res['label'] = lab
                list_mt.append(mt_res)
        return pd.DataFrame.from_dict(list_det), pd.DataFrame.from_dict(list_mt)



class MultiLabelPairwiseMeasures(object):
    # Semantic segmentation or Image wide classification
    def __init__(self, pred, ref,pred_proba,list_values,
                 measures_pcc=[],measures_mt=[],measures_mcc=[],measures_overlap=[],measures_boundary=[], num_neighbors=8, per_case=False,pixdim=[1, 1, 1],
                 empty=False, dict_args={}):
        self.pred = pred
        self.pred_proba = pred_proba
        self.ref = ref
        self.list_values = list_values
        self.measures_binary = measures_pcc + measures_overlap + measures_boundary
        self.measures_mcc = measures_mcc
        self.measures_mt = measures_mt
        self.num_neighbors = num_neighbors
        self.pixdim = pixdim
        self.dict_args = dict_args
        self.per_case = per_case

    def per_label_dict(self):
        list_bin = []
        list_mt = []
        for lab in self.list_values:
            list_pred = []
            list_ref = []
            list_prob = []
            list_case = []
            for case in range(len(self.ref)):
                pred_case = np.asarray(self.pred[case])
                ref_case = np.asarray(self.ref[case])
                prob_case = np.asarray(self.pred_proba[case])
                pred_tmp = np.where(pred_case==lab, np.ones_like(pred_case), np.zeros_like(pred_case))
                pred_proba_tmp = np.where(pred_case==lab, prob_case, np.zeros_like(prob_case))
                ref_tmp = np.where(ref_case==lab, np.ones_like(ref_case), np.zeros_like(ref_case))
                if self.per_case:
                    BPM = BinaryPairwiseMeasures(pred_tmp, ref_tmp, measures_pcc=self.measures_binary, num_neighbors=self.num_neighbors, pixdim=self.pixdim, dict_args=self.dict_args)
                    dict_bin = BPM.to_dict_meas()
                    dict_bin['label'] = lab
                    dict_bin['case'] = case
                    list_bin.append(dict_bin)
                    PPM = ProbabilityPairwiseMeasures(pred_proba=pred_proba_tmp, ref=ref_tmp, measures=self.measures_mt, dict_args=self.dict_args)
                    dict_mt = PPM.to_dict_meas()
                    dict_mt['label'] = lab
                    dict_mt['case'] = case
                    list_mt.append(dict_mt)
                else:
                    list_pred.append(pred_case)
                    list_ref.append(ref_case)
                    list_prob.append(prob_case)
                    list_case.append(np.ones_like(pred_case)*case)
            if not self.per_case:
                overall_pred = np.concatenate(list_pred)
                overall_ref = np.concatenate(list_ref)
                overall_prob = np.concatenate(list_prob)
                BPM = BinaryPairwiseMeasures(overall_pred, overall_ref, measures=self.measures_binary, num_neighbors=self.num_neighbors, pixdim=self.pixdim, dict_args=self.dict_args)
                PPM = ProbabilityPairwiseMeasures(overall_prob, overall_ref,case=list_case, measures=self.measures_mt,dict_args=self.dict_args)
                dict_mt = PPM.to_dict_meas()
                dict_mt['label'] = lab
                dict_bin = BPM.to_dict_meas()
                dict_bin['label'] = lab
                list_bin.append(dict_bin)
                list_mt.append(dict_mt)

        return pd.DataFrame.from_dict(list_bin), pd.DataFrame.from_dict(list_mt)

    

    def multi_label_res(self):
        list_pred = []
        list_ref = []
        list_mcc = []
        for case in range(len(self.ref)):
            pred_case = np.asarray(self.pred[case])
            ref_case = np.asarray(self.ref[case])
            if self.per_case:
                MPM = MultiClassPairwiseMeasures(pred_case,ref_case, self.list_values,measures=self.measures_mcc, dict_args=self.dict_args)
                dict_mcc = MPM.to_dict_meas()
                dict_mcc['case'] = case
                list_mcc.append(dict_mcc)
            else:
                list_pred.append(pred_case)
                list_ref.append(ref_case)
        if self.per_case:
            pd_mcc = pd.DataFrame.from_dict(list_mcc)
        else:
            overall_pred = np.concatenate(list_pred)
            overall_ref = np.concatenate(list_ref)
            MPM = MultiClassPairwiseMeasures(overall_pred,overall_ref, self.list_values,measures=self.measures_mcc, dict_args=self.dict_args)

            dict_mcc = MPM.to_dict_meas()
            list_mcc.append(dict_mcc)
            pd_mcc = pd.DataFrame.from_dict(list_mcc)
        return pd_mcc
